"""
Stockage persistant de HandStats Pro (Supabase).

Remplace tous les fichiers locaux (JSON d'équipes, registre, brouillons, logos...)
par une table unique `kv_store (scope, key, value)` :
  - scope = slug du club (ou "_platform" / "_users" pour les données globales)
  - key   = ancien nom de fichier (ex. "effectif_Séniors_M.json")
  - value = contenu JSON

Configuration (Streamlit Cloud > Settings > Secrets, ou variables d'environnement) :
  SUPABASE_URL, SUPABASE_SERVICE_KEY

Pour tester sans base : HANDSTAT_STORE=memory
"""
from __future__ import annotations

import base64
import json
import os
import threading
from datetime import datetime, timezone

TABLE = "kv_store"
SCOPE_PLATEFORME = "_platform"
SCOPE_UTILISATEURS = "_users"
SCOPE_SESSIONS = "_sessions"


class StockageIndisponible(RuntimeError):
    """Configuration Supabase absente ou incomplète."""


def _secret(nom: str):
    val = os.environ.get(nom)
    if val:
        return val
    try:
        import streamlit as st

        return st.secrets.get(nom)
    except Exception:
        return None


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------
class _Memoire:
    """Backend en mémoire (tests / développement sans base)."""

    def __init__(self):
        self.rows: dict[tuple[str, str], tuple[object, int]] = {}
        self.compteur = 0
        self.lock = threading.Lock()

    def fetch(self, scope, key):
        with self.lock:
            r = self.rows.get((scope, key))
            return None if r is None else (json.loads(json.dumps(r[0])), r[1])

    def fetch_version(self, scope, key):
        with self.lock:
            r = self.rows.get((scope, key))
            return None if r is None else r[1]

    def upsert(self, scope, key, value):
        with self.lock:
            self.compteur += 1
            self.rows[(scope, key)] = (json.loads(json.dumps(value)), self.compteur)
            return self.compteur

    def cas(self, scope, key, value, version_attendue):
        with self.lock:
            r = self.rows.get((scope, key))
            if version_attendue is None:
                if r is not None:
                    return None
            elif r is None or r[1] != version_attendue:
                return None
            self.compteur += 1
            self.rows[(scope, key)] = (json.loads(json.dumps(value)), self.compteur)
            return self.compteur

    def remove(self, scope, key):
        with self.lock:
            self.rows.pop((scope, key), None)

    def list_keys(self, scope):
        with self.lock:
            return [k for (s, k) in self.rows if s == scope]

    def fetch_scope(self, scope):
        with self.lock:
            return {k: json.loads(json.dumps(v[0])) for (s, k), v in self.rows.items() if s == scope}

    def remove_scope(self, scope):
        with self.lock:
            for cle in [c for c in self.rows if c[0] == scope]:
                del self.rows[cle]


class _Supabase:
    def __init__(self, url: str, cle: str):
        from supabase import create_client

        self.c = create_client(url, cle)

    def _t(self):
        return self.c.table(TABLE)

    def fetch(self, scope, key):
        r = self._t().select("value,updated_at").eq("scope", scope).eq("key", key).limit(1).execute()
        if not r.data:
            return None
        return r.data[0]["value"], r.data[0]["updated_at"]

    def fetch_version(self, scope, key):
        r = self._t().select("updated_at").eq("scope", scope).eq("key", key).limit(1).execute()
        return r.data[0]["updated_at"] if r.data else None

    def upsert(self, scope, key, value):
        r = (
            self._t()
            .upsert(
                {"scope": scope, "key": key, "value": value, "updated_at": _maintenant()},
                on_conflict="scope,key",
            )
            .execute()
        )
        return r.data[0]["updated_at"] if r.data else None

    def cas(self, scope, key, value, version_attendue):
        """Écrit seulement si la ligne n'a pas changé depuis `version_attendue`
        (None = création : échoue si la ligne existe déjà). Retourne la nouvelle version, ou None si conflit."""
        ligne = {"scope": scope, "key": key, "value": value, "updated_at": _maintenant()}
        if version_attendue is None:
            try:
                r = self._t().insert(ligne).execute()
            except Exception as exc:
                texte = str(exc).lower()
                if "23505" in texte or "duplicate" in texte:
                    return None
                raise
            return r.data[0]["updated_at"] if r.data else ligne["updated_at"]
        r = (
            self._t()
            .update({"value": value, "updated_at": ligne["updated_at"]})
            .eq("scope", scope)
            .eq("key", key)
            .eq("updated_at", version_attendue)
            .execute()
        )
        return r.data[0]["updated_at"] if r.data else None

    def remove(self, scope, key):
        self._t().delete().eq("scope", scope).eq("key", key).execute()

    def list_keys(self, scope):
        r = self._t().select("key").eq("scope", scope).execute()
        return [row["key"] for row in (r.data or [])]

    def fetch_scope(self, scope):
        r = self._t().select("key,value").eq("scope", scope).execute()
        return {row["key"]: row["value"] for row in (r.data or [])}

    def remove_scope(self, scope):
        self._t().delete().eq("scope", scope).execute()


_BACKEND = None
_LOCK = threading.Lock()
# Cache : (scope, key) -> (version, texte_json). Une requête légère de version
# valide le cache à chaque lecture : on ne retélécharge que si la donnée a changé.
_CACHE: dict[tuple[str, str], tuple[object, str]] = {}


def _backend():
    global _BACKEND
    if _BACKEND is None:
        with _LOCK:
            if _BACKEND is None:
                if os.environ.get("HANDSTAT_STORE") == "memory":
                    _BACKEND = _Memoire()
                else:
                    url = _secret("SUPABASE_URL")
                    cle = _secret("SUPABASE_SERVICE_KEY")
                    if not url or not cle:
                        raise StockageIndisponible(
                            "SUPABASE_URL et SUPABASE_SERVICE_KEY doivent être définis dans les secrets."
                        )
                    _BACKEND = _Supabase(url, cle)
    return _BACKEND


# ---------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------
def get_json(scope: str, key: str, default=None, immuable: bool = False):
    """immuable=True : la donnée ne change jamais une fois écrite (ex. détail d'un match archivé) ;
    si elle est en cache, on la renvoie sans interroger la base."""
    b = _backend()
    ck = (scope, key)
    en_cache = _CACHE.get(ck)
    if en_cache is not None and immuable:
        return json.loads(en_cache[1])
    if en_cache is not None:
        version = b.fetch_version(scope, key)
        if version is None:
            _CACHE.pop(ck, None)
            return default
        if version == en_cache[0]:
            return json.loads(en_cache[1])
    r = b.fetch(scope, key)
    if r is None:
        _CACHE.pop(ck, None)
        return default
    valeur, version = r
    _CACHE[ck] = (version, json.dumps(valeur, ensure_ascii=False))
    return valeur


def set_json(scope: str, key: str, valeur) -> None:
    texte = json.dumps(valeur, ensure_ascii=False)  # échoue tôt si non sérialisable
    version = _backend().upsert(scope, key, json.loads(texte))
    if version is None:
        _CACHE.pop((scope, key), None)
    else:
        _CACHE[(scope, key)] = (version, texte)


def lire_avec_version(scope: str, key: str):
    """(valeur, version) lus directement en base (sans cache), ou None si la ligne n'existe pas."""
    return _backend().fetch(scope, key)


def lire_version(scope: str, key: str):
    """Version actuelle d'une ligne (requête très légère), ou None si elle n'existe pas."""
    return _backend().fetch_version(scope, key)


def cas_json(scope: str, key: str, valeur, version_attendue):
    """Écriture conditionnelle (compare-and-swap). Retourne la nouvelle version, ou None s'il y a eu conflit
    (quelqu'un d'autre a écrit entre-temps). version_attendue=None : création uniquement."""
    texte = json.dumps(valeur, ensure_ascii=False)
    version = _backend().cas(scope, key, json.loads(texte), version_attendue)
    if version is not None:
        _CACHE[(scope, key)] = (version, texte)
    return version


def delete_json(scope: str, key: str) -> None:
    _backend().remove(scope, key)
    _CACHE.pop((scope, key), None)


def list_keys(scope: str) -> list[str]:
    return _backend().list_keys(scope)


def dump_scope(scope: str) -> dict:
    """Retourne {key: value} pour tout un scope (sauvegardes, registre)."""
    return _backend().fetch_scope(scope)


def supprimer_scope(scope: str) -> None:
    _backend().remove_scope(scope)
    for ck in [c for c in _CACHE if c[0] == scope]:
        _CACHE.pop(ck, None)


# --- Fichiers binaires (logos) ---------------------------------------
def set_bytes(scope: str, key: str, data: bytes, mime: str = "image/png") -> None:
    set_json(scope, key, {"b64": base64.b64encode(data).decode("ascii"), "mime": mime})


def get_bytes(scope: str, key: str) -> bytes | None:
    v = get_json(scope, key, None)
    if isinstance(v, dict) and v.get("b64"):
        try:
            return base64.b64decode(v["b64"])
        except Exception:
            return None
    return None


# --- Migration depuis l'ancien stockage sur disque -------------------
def importer_dossier_club(slug: str, dossier: str) -> int:
    """Importe les JSON d'équipes et les logos d'un ancien dossier club. Retourne le nombre d'éléments."""
    if not dossier or not os.path.isdir(dossier):
        return 0
    n = 0
    for nom in os.listdir(dossier):
        chemin = os.path.join(dossier, nom)
        if not os.path.isfile(chemin):
            continue
        bas = nom.lower()
        try:
            if bas.endswith(".json"):
                with open(chemin, "r", encoding="utf-8") as f:
                    set_json(slug, nom, json.load(f))
                n += 1
            elif bas.endswith((".png", ".jpg", ".jpeg", ".webp")):
                with open(chemin, "rb") as f:
                    set_bytes(slug, nom, f.read(), mime="image/png" if bas.endswith(".png") else "image/jpeg")
                n += 1
        except Exception:
            continue
    return n
