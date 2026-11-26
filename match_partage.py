"""
Match en direct PARTAGÉ : plusieurs staffs d'une même équipe saisissent le même match,
avec un chrono commun et des données communes sur tous les écrans.

Principe
- L'état du match (le « brouillon ») est stocké une seule fois dans Supabase.
- Chaque staff publie son état après chaque action. Si quelqu'un d'autre a publié entre-temps,
  les deux versions sont FUSIONNÉES (et non écrasées) :
    * journal d'actions et notes : les ajouts des deux sont conservés (identifiant unique par ligne) ;
    * compteurs (buts, tirs, arrêts, zones...) : on additionne les variations de chacun ;
    * chrono, période, rotations : la dernière modification gagne, par bloc cohérent ;
    * temps de jeu : on garde la valeur la plus élevée.
- L'écriture est atomique (compare-and-swap) : en cas de collision, on relit, on refusionne, on réessaie.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from supabase_store import cas_json, delete_json, dump_scope, lire_avec_version, lire_version, set_json

LISTES_AVEC_ID = ("journal_actions", "commentaires_staff")
COMPTEURS = ("stats_membres", "zones_tirs_match", "attaques_adversaires", "temps_morts")
MAXIMUMS = ("temps_jeu_secondes",)
LOCAUX = ("joueuse_focus_live",)          # sélection personnelle : jamais partagée
GROUPES = (                               # champs qui doivent rester cohérents entre eux
    ("periode_match", "chrono_en_cours", "chrono_debut", "chrono_secondes_cumulees"),
    ("terrain_joueuses", "banc_joueuses"),
)
IDENTITE = {"numero", "type", "nom", "poste"}   # dans stats_membres : informations, pas des compteurs
MAX_ESSAIS = 10
MATCH_ABANDONNE_APRES_S = 6 * 3600


class ConflitPersistant(RuntimeError):
    """Impossible de publier après plusieurs essais (très forte activité simultanée)."""


@dataclass
class Resultat:
    etat: dict | None      # état fusionné (None si le match n'existe plus)
    version: object | None
    fusion: bool           # True si des modifications d'autres staffs ont été intégrées
    termine: bool          # True si le match a été terminé / annulé par quelqu'un d'autre


# ----------------------------------------------------------------------
# Identifiants des lignes de journal
# ----------------------------------------------------------------------
def normaliser_ids(snapshot: dict) -> dict:
    """Donne un identifiant STABLE aux anciennes lignes qui n'en ont pas (brouillons d'avant le partage)."""
    for champ in LISTES_AVEC_ID:
        for idx, e in enumerate(snapshot.get(champ) or []):
            if isinstance(e, dict) and "_id" not in e:
                brut = json.dumps(e, sort_keys=True, ensure_ascii=False, default=str) + f"#{idx}"
                e["_id"] = "L" + hashlib.sha1(brut.encode("utf-8")).hexdigest()[:11]
    return snapshot


def assigner_ids_nouveaux(snapshot: dict) -> dict:
    """Identifiant unique pour les lignes créées par cette session."""
    for champ in LISTES_AVEC_ID:
        for e in snapshot.get(champ) or []:
            if isinstance(e, dict) and "_id" not in e:
                e["_id"] = uuid.uuid4().hex[:12]
    return snapshot


# ----------------------------------------------------------------------
# Fusion à trois voies : base (état que j'avais) / mine (mon état) / theirs (état actuel partagé)
# ----------------------------------------------------------------------
def _nombre(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def fusion_liste_id(base, mine, theirs) -> list:
    ids_base = {e["_id"] for e in (base or []) if isinstance(e, dict) and "_id" in e}
    ids_mine = {e["_id"] for e in (mine or []) if isinstance(e, dict) and "_id" in e}
    supprimes = ids_base - ids_mine                                   # lignes que j'ai annulées
    nouveaux = [e for e in (mine or []) if isinstance(e, dict) and e.get("_id") not in ids_base]
    resultat = [e for e in (theirs or []) if not (isinstance(e, dict) and e.get("_id") in supprimes)]
    deja = {e.get("_id") for e in resultat if isinstance(e, dict)}
    resultat += [e for e in nouveaux if e.get("_id") not in deja]
    return resultat


def fusion_compteurs(base, mine, theirs, ignorer=frozenset()):
    """Additionne les variations : résultat = theirs + (mine - base), jamais négatif."""
    if any(isinstance(x, dict) for x in (base, mine, theirs)):
        b = base if isinstance(base, dict) else {}
        m = mine if isinstance(mine, dict) else {}
        t = theirs if isinstance(theirs, dict) else {}
        sortie = {}
        for cle in list(t) + [k for k in m if k not in t]:
            if cle in ignorer:
                sortie[cle] = m[cle] if (cle in m and m.get(cle) != b.get(cle)) else t.get(cle, m.get(cle))
            elif cle not in t:
                sortie[cle] = copy.deepcopy(m[cle])
            elif cle not in m:
                sortie[cle] = copy.deepcopy(t[cle])
            else:
                sortie[cle] = fusion_compteurs(b.get(cle), m[cle], t[cle], ignorer)
        return sortie
    if _nombre(mine) or _nombre(theirs):
        b = base if _nombre(base) else 0
        m = mine if _nombre(mine) else b
        t = theirs if _nombre(theirs) else b
        res = max(0, t + (m - b))
        return int(res) if all(isinstance(v, int) for v in (b, m, t)) else res
    return mine if mine != base else theirs


def fusion_max(mine, theirs):
    if isinstance(mine, dict) or isinstance(theirs, dict):
        m = mine if isinstance(mine, dict) else {}
        t = theirs if isinstance(theirs, dict) else {}
        return {k: fusion_max(m.get(k), t.get(k)) for k in list(t) + [k for k in m if k not in t]}
    if _nombre(mine) and _nombre(theirs):
        return max(mine, theirs)
    return theirs if theirs is not None else mine


def fusionner(base: dict | None, mine: dict, theirs: dict) -> dict:
    base = base or {}
    groupes = {c for g in GROUPES for c in g}
    resultat: dict = {}
    for cle in list(theirs) + [k for k in mine if k not in theirs]:
        if cle in groupes or cle in LOCAUX:
            continue
        if cle in LISTES_AVEC_ID:
            resultat[cle] = fusion_liste_id(base.get(cle), mine.get(cle), theirs.get(cle))
        elif cle in COMPTEURS:
            resultat[cle] = fusion_compteurs(base.get(cle), mine.get(cle), theirs.get(cle), IDENTITE)
        elif cle in MAXIMUMS:
            resultat[cle] = fusion_max(mine.get(cle), theirs.get(cle))
        else:  # dernier écrivain : ma valeur si je l'ai modifiée, sinon celle de l'autre
            resultat[cle] = copy.deepcopy(mine[cle] if (cle in mine and mine.get(cle) != base.get(cle)) else theirs.get(cle, mine.get(cle)))
    for groupe in GROUPES:
        modifie = any(mine.get(c) != base.get(c) for c in groupe)
        source = mine if modifie else theirs
        for c in groupe:
            if c in source:
                resultat[c] = copy.deepcopy(source[c])
    for cle in LOCAUX:
        if cle in mine or cle in theirs:
            resultat[cle] = mine.get(cle, theirs.get(cle))
    return resultat


# ----------------------------------------------------------------------
# Accès au match partagé
# ----------------------------------------------------------------------
def _maintenant_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PartageMatch:
    """Match en direct d'une équipe, stocké sous la clé du brouillon (compatible avec l'existant)."""

    def __init__(self, scope: str, cle: str, ctx: str = ""):
        self.scope, self.cle, self.ctx = scope, cle, ctx
        self._prefixe_presence = f"presence_{cle}__"

    # --- lecture ---
    def lire(self):
        """(état, version, enveloppe) ou None s'il n'y a pas de match en cours."""
        r = lire_avec_version(self.scope, self.cle)
        if r is None:
            return None
        enveloppe, version = r
        etat = enveloppe.get("state") if isinstance(enveloppe, dict) else None
        if not isinstance(etat, dict):
            return None
        normaliser_ids(etat)
        return etat, version, enveloppe

    def version(self):
        return lire_version(self.scope, self.cle)

    def match_actif(self):
        """Enveloppe du match en cours si elle est récente (< 6 h), sinon None."""
        lu = self.lire()
        if not lu or not lu[0].get("joueuses_actives"):
            return None
        try:
            maj = datetime.fromisoformat(lu[2].get("updated_at", ""))
            if (datetime.now(timezone.utc) - maj).total_seconds() > MATCH_ABANDONNE_APRES_S:
                return None
        except Exception:
            pass
        return lu

    # --- écriture ---
    def _enveloppe(self, etat: dict, auteur: str, utilisateur: str):
        return {"ctx_prefix": self.ctx, "updated_at": _maintenant_iso(), "maj_par": auteur,
                "maj_par_user": utilisateur, "state": etat}

    def creer(self, etat: dict, auteur: str, utilisateur: str = ""):
        """Démarre un match partagé (remplace un ancien brouillon abandonné). Retourne (état, version)."""
        etat = assigner_ids_nouveaux(copy.deepcopy(etat))
        etat.setdefault("createur", auteur)
        for _ in range(MAX_ESSAIS):
            actuel = lire_avec_version(self.scope, self.cle)
            version = cas_json(self.scope, self.cle, self._enveloppe(etat, auteur, utilisateur),
                               None if actuel is None else actuel[1])
            if version is not None:
                return etat, version
        raise ConflitPersistant("création du match impossible")

    def publier(self, base: dict | None, mine: dict, auteur: str, utilisateur: str = "", base_version=None) -> Resultat:
        mine = assigner_ids_nouveaux(copy.deepcopy(mine))
        if base_version is not None:
            # Cas courant (personne d'autre n'a écrit) : une seule écriture conditionnelle, sans relire le match.
            if base:
                mine.setdefault("createur", base.get("createur", auteur))
            rapide = cas_json(self.scope, self.cle, self._enveloppe(mine, auteur, utilisateur), base_version)
            if rapide is not None:
                return Resultat(mine, rapide, False, False)
            base_version = None                                      # quelqu'un a écrit entre-temps : voie complète
        for tentative in range(MAX_ESSAIS):
            actuel = lire_avec_version(self.scope, self.cle)
            if actuel is None:
                return Resultat(None, None, False, True)
            enveloppe, version = actuel
            theirs = normaliser_ids(copy.deepcopy(enveloppe.get("state") or {}))
            if base_version is not None and version == base_version:
                fusionne, fusion = mine, False                       # personne d'autre n'a écrit : simple publication
            else:
                fusionne, fusion = fusionner(base or theirs, mine, theirs), True
            if fusionne == theirs:
                return Resultat(fusionne, version, fusion, False)    # rien de nouveau à écrire
            fusionne.setdefault("createur", theirs.get("createur", auteur))
            nouvelle = self._enveloppe(fusionne, auteur, utilisateur)
            nouvelle_version = cas_json(self.scope, self.cle, nouvelle, version)
            if nouvelle_version is not None:
                return Resultat(fusionne, nouvelle_version, fusion, False)
            base_version = None                                      # collision : on relit et on refusionne
            time.sleep(min(0.05 * (tentative + 1), 0.25))
        raise ConflitPersistant("trop de modifications simultanées")

    def terminer(self) -> None:
        delete_json(self.scope, self.cle)
        try:
            for k in dump_scope(self.scope, self._prefixe_presence):
                delete_json(self.scope, k)
        except Exception:
            pass

    # --- présence (qui est connecté sur ce match) ---
    def battement(self, sid: str, nom: str) -> None:
        set_json(self.scope, self._prefixe_presence + sid, {"sid": sid, "nom": nom, "ts": time.time()})

    def participants(self, delai: float = 25.0) -> list[dict]:
        actifs, maintenant = [], time.time()
        for k, v in dump_scope(self.scope, self._prefixe_presence).items():     # une seule requête
            if not isinstance(v, dict):
                continue
            age = maintenant - float(v.get("ts", 0))
            if age <= delai:
                actifs.append(v)
            elif age > 2 * 3600:
                delete_json(self.scope, k)                           # ménage des anciennes sessions
        return sorted(actifs, key=lambda p: p["sid"])
