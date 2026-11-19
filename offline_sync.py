import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OfflineSyncManager:
    """Gestion locale des brouillons de match en cours et de la file d'attente de synchronisation."""

    def __init__(self, dossier_club: str, club_slug: str):
        self.dossier_club = Path(dossier_club)
        self.club_slug = club_slug
        self.sync_dir = self.dossier_club / "offline_sync"
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = self.sync_dir / f"queue_{self.club_slug}.json"
        if not self.queue_path.exists():
            self._write_json(self.queue_path, {"items": []})

    def _read_json(self, path: Path, default):
        try:
            if not path.exists():
                return default
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _write_json(self, path: Path, payload):
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    # --- Brouillon local du match en cours ---
    def draft_file(self, ctx_prefix: str) -> Path:
        safe_prefix = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in ctx_prefix)
        return self.sync_dir / f"draft_{safe_prefix}.json"

    def sauvegarder_brouillon(self, ctx_prefix: str, state_data: dict) -> None:
        payload = {
            "ctx_prefix": ctx_prefix,
            "updated_at": _now_iso(),
            "state": state_data,
        }
        self._write_json(self.draft_file(ctx_prefix), payload)

    def charger_brouillon(self, ctx_prefix: str) -> dict | None:
        data = self._read_json(self.draft_file(ctx_prefix), None)
        if isinstance(data, dict) and isinstance(data.get("state"), dict):
            return data
        return None

    def supprimer_brouillon(self, ctx_prefix: str) -> None:
        path = self.draft_file(ctx_prefix)
        if path.exists():
            path.unlink()

    # --- File d'attente de synchronisation ---
    def ajouter_operation(self, op_type: str, equipe_nom: str, payload: dict) -> str:
        queue_data = self._read_json(self.queue_path, {"items": []})
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
        self._write_json(self.queue_path, {"items": items})
        return op_id

    def lister_en_attente(self) -> list[dict]:
        queue_data = self._read_json(self.queue_path, {"items": []})
        return [it for it in queue_data.get("items", []) if it.get("status") in ("pending", "error")]

    def synchroniser_tout(self, handler_fn) -> dict:
        queue_data = self._read_json(self.queue_path, {"items": []})
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

        self._write_json(self.queue_path, {"items": items})
        return {"synced": synced_count, "failed": failed_count}

    def purger_synchronises(self) -> int:
        queue_data = self._read_json(self.queue_path, {"items": []})
        items = queue_data.get("items", [])
        restants = [it for it in items if it.get("status") != "synced"]
        supprimes = len(items) - len(restants)
        if supprimes > 0:
            self._write_json(self.queue_path, {"items": restants})
        return supprimes