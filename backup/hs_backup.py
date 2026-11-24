#!/usr/bin/env python3
"""
Sauvegarde et restauration CHIFFRÉES de la base HandStats Pro (table kv_store de Supabase).

  Exporter :   python hs_backup.py exporter --sortie sauvegarde.hsbk
  Contenu :    python hs_backup.py contenu   --fichier sauvegarde.hsbk
  Restaurer :  python hs_backup.py restaurer --fichier sauvegarde.hsbk            (simulation, ne change rien)
               python hs_backup.py restaurer --fichier sauvegarde.hsbk --appliquer

Variables d'environnement :
  SUPABASE_URL, SUPABASE_SERVICE_KEY   accès à la base (clé secrète service_role)
  BACKUP_PASSPHRASE                    phrase secrète de chiffrement (12 caractères minimum)

Dépendance : pip install cryptography
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

MAGIC = b"HSBK1"
FORMAT = "handstats-kv-v1"
TABLE = "kv_store"
SCOPES_EXCLUS = {"_sessions"}   # jetons de connexion : inutiles à sauvegarder et sensibles
TAILLE_PAGE = 200
LOT_RESTAURATION = 50


# ----------------------------------------------------------------------
# Chiffrement (AES-256-GCM, clé dérivée de la phrase secrète par scrypt)
# ----------------------------------------------------------------------
def _cle(phrase: str, sel: bytes) -> bytes:
    return hashlib.scrypt(phrase.encode("utf-8"), salt=sel, n=2**15, r=8, p=1, dklen=32, maxmem=128 * 1024 * 1024)


def chiffrer(octets: bytes, phrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    sel, nonce = os.urandom(16), os.urandom(12)
    return MAGIC + sel + nonce + AESGCM(_cle(phrase, sel)).encrypt(nonce, octets, MAGIC)


def dechiffrer(contenu: bytes, phrase: str) -> bytes:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not contenu.startswith(MAGIC) or len(contenu) < len(MAGIC) + 28:
        raise SystemExit("Fichier illisible : ce n'est pas une sauvegarde HandStats Pro.")
    sel = contenu[len(MAGIC): len(MAGIC) + 16]
    nonce = contenu[len(MAGIC) + 16: len(MAGIC) + 28]
    try:
        return AESGCM(_cle(phrase, sel)).decrypt(nonce, contenu[len(MAGIC) + 28:], MAGIC)
    except InvalidTag:
        raise SystemExit("Déchiffrement impossible : phrase secrète incorrecte ou fichier corrompu.")


def _phrase() -> str:
    phrase = os.environ.get("BACKUP_PASSPHRASE", "")
    if len(phrase) < 12:
        raise SystemExit("BACKUP_PASSPHRASE manquante ou trop courte (12 caractères minimum).")
    return phrase


# ----------------------------------------------------------------------
# Accès à la base (API REST de Supabase, sans dépendance externe)
# ----------------------------------------------------------------------
def _config() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    cle = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not cle:
        raise SystemExit("SUPABASE_URL et SUPABASE_SERVICE_KEY doivent être définis.")
    return url, cle


def _requete(methode: str, params: dict | None = None, corps=None, entetes: dict | None = None):
    url, cle = _config()
    adresse = f"{url}/rest/v1/{TABLE}"
    if params:
        adresse += "?" + urllib.parse.urlencode(params)
    en_tetes = {"apikey": cle, "Authorization": f"Bearer {cle}", "Content-Type": "application/json"}
    en_tetes.update(entetes or {})
    donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8") if corps is not None else None

    derniere_erreur = None
    for tentative in range(4):
        try:
            req = urllib.request.Request(adresse, data=donnees, headers=en_tetes, method=methode)
            with urllib.request.urlopen(req, timeout=90) as rep:
                return rep.read(), rep.headers
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code < 500 and exc.code != 429:
                raise SystemExit(f"Erreur Supabase {exc.code} : {detail}")
            derniere_erreur = f"HTTP {exc.code} {detail}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            derniere_erreur = str(exc)
        time.sleep(2 * (tentative + 1))
    raise SystemExit(f"Supabase injoignable après plusieurs essais : {derniere_erreur}")


def lire_toutes_les_lignes() -> list[dict]:
    """Lit toute la table par pages et vérifie le nombre de lignes reçues."""
    for essai in range(3):
        lignes, offset, total = [], 0, None
        while True:
            corps, entetes = _requete(
                "GET",
                {"select": "scope,key,value,updated_at", "order": "scope.asc,key.asc", "limit": TAILLE_PAGE, "offset": offset},
                entetes={"Prefer": "count=exact"},
            )
            page = json.loads(corps)
            plage = entetes.get("Content-Range", "")
            if "/" in plage and plage.rsplit("/", 1)[1].isdigit():
                total = int(plage.rsplit("/", 1)[1])
            lignes.extend(page)
            if len(page) < TAILLE_PAGE:
                break
            offset += TAILLE_PAGE
        if total is None or len(lignes) == total:
            return lignes
        time.sleep(5)  # des écritures ont eu lieu pendant la lecture : on recommence
    raise SystemExit("Lecture incohérente de la base (données modifiées pendant l'export). Réessayez.")


# ----------------------------------------------------------------------
# Commandes
# ----------------------------------------------------------------------
def _resume(lignes: list[dict]) -> dict[str, int]:
    par_scope: dict[str, int] = {}
    for l in lignes:
        par_scope[l["scope"]] = par_scope.get(l["scope"], 0) + 1
    return dict(sorted(par_scope.items()))


def cmd_exporter(args) -> None:
    phrase = _phrase()
    toutes = lire_toutes_les_lignes()
    lignes = [l for l in toutes if l["scope"] not in SCOPES_EXCLUS]
    if not lignes and not args.autoriser_vide:
        raise SystemExit("La base est vide : sauvegarde annulée (anomalie probable). Utilisez --autoriser-vide si c'est voulu.")

    charge = {
        "format": FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nb_lignes": len(lignes),
        "lignes": lignes,
    }
    brut = gzip.compress(json.dumps(charge, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    contenu = chiffrer(brut, phrase)

    sortie = args.sortie or f"handstats_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.hsbk"
    with open(sortie, "wb") as f:
        f.write(contenu)

    # Vérification : on relit et on déchiffre le fichier qu'on vient d'écrire.
    with open(sortie, "rb") as f:
        relu = json.loads(gzip.decompress(dechiffrer(f.read(), phrase)))
    if relu["nb_lignes"] != len(lignes) or len(relu["lignes"]) != len(lignes):
        raise SystemExit("Vérification échouée : le fichier écrit ne correspond pas aux données lues.")

    print(f"Sauvegarde OK : {len(lignes)} lignes, {len(contenu) / 1024:.0f} Ko -> {sortie}")
    for scope, n in _resume(lignes).items():
        print(f"  - {scope}: {n}")


def _charger_fichier(chemin: str) -> dict:
    with open(chemin, "rb") as f:
        donnees = json.loads(gzip.decompress(dechiffrer(f.read(), _phrase())))
    if donnees.get("format") != FORMAT:
        raise SystemExit("Format de sauvegarde non reconnu.")
    return donnees


def cmd_contenu(args) -> None:
    d = _charger_fichier(args.fichier)
    print(f"Sauvegarde du {d['exported_at']} : {d['nb_lignes']} lignes")
    for scope, n in _resume(d["lignes"]).items():
        print(f"  - {scope}: {n}")


def _supprimer_ligne(scope: str, cle: str) -> None:
    _requete("DELETE", {"scope": f"eq.{scope}", "key": f"eq.{cle}"})


def cmd_restaurer(args) -> None:
    d = _charger_fichier(args.fichier)
    lignes = d["lignes"]
    if args.scope:
        lignes = [l for l in lignes if l["scope"] in set(args.scope)]
        if not lignes:
            raise SystemExit(f"Aucune donnée pour : {', '.join(args.scope)}")

    print(f"Sauvegarde du {d['exported_at']}.")
    print(f"À restaurer : {len(lignes)} lignes")
    for scope, n in _resume(lignes).items():
        print(f"  - {scope}: {n}")

    scopes_cibles = sorted({l["scope"] for l in lignes})
    en_trop: list[tuple[str, str]] = []
    if args.remplacer:
        presentes = {(l["scope"], l["key"]) for l in lignes}
        for l in lire_toutes_les_lignes():
            if l["scope"] in scopes_cibles and (l["scope"], l["key"]) not in presentes:
                en_trop.append((l["scope"], l["key"]))
        print(f"Lignes actuelles absentes de la sauvegarde, à SUPPRIMER (--remplacer) : {len(en_trop)}")

    if not args.appliquer:
        print("\nSIMULATION : rien n'a été modifié. Ajoutez --appliquer pour restaurer réellement.")
        return

    if not args.oui:
        if input("\nCela ÉCRASE les données actuelles correspondantes. Tapez RESTAURER pour confirmer : ").strip() != "RESTAURER":
            raise SystemExit("Annulé.")

    for i in range(0, len(lignes), LOT_RESTAURATION):
        lot = [{"scope": l["scope"], "key": l["key"], "value": l["value"], "updated_at": l["updated_at"]}
               for l in lignes[i: i + LOT_RESTAURATION]]
        _requete("POST", {"on_conflict": "scope,key"}, corps=lot,
                 entetes={"Prefer": "resolution=merge-duplicates,return=minimal"})
    for scope, cle in en_trop:
        _supprimer_ligne(scope, cle)
    print(f"\nRestauration terminée : {len(lignes)} lignes écrites, {len(en_trop)} supprimées.")


def main() -> None:
    p = argparse.ArgumentParser(description="Sauvegarde / restauration chiffrée de HandStats Pro")
    sp = p.add_subparsers(dest="commande", required=True)

    e = sp.add_parser("exporter", help="exporte la base dans un fichier chiffré")
    e.add_argument("--sortie", help="nom du fichier (par défaut handstats_AAAAMMJJ_HHMMSS.hsbk)")
    e.add_argument("--autoriser-vide", action="store_true")
    e.set_defaults(fn=cmd_exporter)

    c = sp.add_parser("contenu", help="affiche le contenu d'une sauvegarde")
    c.add_argument("--fichier", required=True)
    c.set_defaults(fn=cmd_contenu)

    r = sp.add_parser("restaurer", help="restaure une sauvegarde (simulation par défaut)")
    r.add_argument("--fichier", required=True)
    r.add_argument("--scope", action="append", help="ne restaurer que ce club (slug) ; répétable")
    r.add_argument("--remplacer", action="store_true",
                   help="supprime aussi les données actuelles absentes de la sauvegarde (retour exact à l'état sauvegardé)")
    r.add_argument("--appliquer", action="store_true", help="écrit réellement dans la base")
    r.add_argument("--oui", action="store_true", help="ne pas demander de confirmation")
    r.set_defaults(fn=cmd_restaurer)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

