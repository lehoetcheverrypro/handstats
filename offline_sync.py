import uuid
from datetime import datetime, timezone
from pathlib import Path

from supabase_store import delete_json, get_json, set_json


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OfflineSyncManager:
    """Brouillons de match en cours et file d'attente de synchronisation, stockés dans Supabase
    (ils survivent donc aux redémarrages et mises à jour de l'application)."""

    def __init__(self, dossier_club: str, club_slug: str):
        self.dossier_club = Path(dossier_club)   # conservé pour compatibilité
        self.club_slug = club_slug
        self.queue_key = f"offline_queue_{self.club_slug}"

    def _read(self, key: str, default):
        try:
            valeur = get_json(self.club_slug, key, None)
            return default if valeur is None else valeur
        except Exception:
            return default

    def _write(self, key: str, payload) -> None:
        set_json(self.club_slug, key, payload)

    # --- Brouillon du match en cours ---
    def draft_key(self, ctx_prefix: str) -> str:
        safe_prefix = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in ctx_prefix)
        return f"draft_{safe_prefix}"

    def sauvegarder_brouillon(self, ctx_prefix: str, state_data: dict) -> None:
        payload = {
            "ctx_prefix": ctx_prefix,
            "updated_at": _now_iso(),
            "state": state_data,
        }
        try:
            self._write(self.draft_key(ctx_prefix), payload)
        except Exception:
            pass  # un échec ponctuel de sauvegarde du brouillon ne doit pas interrompre le match

    def charger_brouillon(self, ctx_prefix: str) -> dict | None:
        data = self._read(self.draft_key(ctx_prefix), None)
        if isinstance(data, dict) and isinstance(data.get("state"), dict):
            return data
        return None

    def supprimer_brouillon(self, ctx_prefix: str) -> None:
        try:
            delete_json(self.club_slug, self.draft_key(ctx_prefix))
        except Exception:
            pass

    # --- File d'attente de synchronisation ---
    def ajouter_operation(self, op_type: str, equipe_nom: str, payload: dict) -> str:
        queue_data = self._read(self.queue_key, {"items": []})
        items = queue_data.get("items", [])

        op_id = str(uuid.uuid4())
        entry = {
            "op_id": op_id,
            "op_type": op_type,
            "club_slug": self.club_slug,
            "equipe_nom": equipe_nom,
            "created_at": _now_iso(),
            "synced_at": None,
            "status": "pending",
            "error_msg": None,
            "payload": payload,
        }
        items.append(entry)
        self._write(self.queue_key, {"items": items})
        return op_id

    def lister_en_attente(self) -> list[dict]:
        queue_data = self._read(self.queue_key, {"items": []})
        return [it for it in queue_data.get("items", []) if it.get("status") in ("pending", "error")]

    def synchroniser_tout(self, handler_fn) -> dict:
        queue_data = self._read(self.queue_key, {"items": []})
        items = queue_data.get("items", [])
        synced_count = 0
        failed_count = 0

        for it in items:
            if it.get("status") in ("pending", "error"):
                try:
                    handler_fn(it)
                    it["status"] = "synced"
                    it["synced_at"] = _now_iso()
                    it["error_msg"] = None
                    synced_count += 1
                except Exception as exc:
                    it["status"] = "error"
                    it["error_msg"] = str(exc)
                    failed_count += 1

        self._write(self.queue_key, {"items": items})
        return {"synced": synced_count, "failed": failed_count}

    def purger_synchronises(self) -> int:
        queue_data = self._read(self.queue_key, {"items": []})
        items = queue_data.get("items", [])
        restants = [it for it in items if it.get("status") != "synced"]
        supprimes = len(items) - len(restants)
        if supprimes > 0:
            self._write(self.queue_key, {"items": restants})
        return supprimes
