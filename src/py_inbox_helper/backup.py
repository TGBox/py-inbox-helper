"""Backup and rollback engine for safe email restructuring."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from py_inbox_helper.models import BackupItemState, BackupSnapshot, EmailItem


class BackupManager:
    """Manages creation, storage, and full restoration of email state snapshots."""

    def __init__(self, backup_dir: Optional[Path] = None):
        if backup_dir is None:
            self.backup_dir = Path.home() / ".py_inbox_helper" / "backups"
        else:
            self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, account_name: str, emails: List[EmailItem]) -> BackupSnapshot:
        """Creates a snapshot representing the exact state of emails prior to actions."""
        now = datetime.now(timezone.utc)
        snapshot_id = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        items = [
            BackupItemState(
                id=e.id,
                entry_id=e.entry_id,
                store_id=e.store_id,
                folder_path=e.folder_path,
                is_read=e.is_read,
                importance=e.importance,
                categories=list(e.categories),
                subject=e.subject,
            )
            for e in emails
        ]
        return BackupSnapshot(
            snapshot_id=snapshot_id,
            created_at=now,
            account_name=account_name,
            items=items,
        )

    def save_snapshot(self, snapshot: BackupSnapshot) -> Path:
        """Persists the snapshot to a local JSON file."""
        file_path = self.backup_dir / f"{snapshot.snapshot_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)
        return file_path

    def load_snapshot(self, snapshot_id: str) -> Optional[BackupSnapshot]:
        """Loads a snapshot by its ID or filename."""
        clean_id = snapshot_id.replace(".json", "")
        file_path = self.backup_dir / f"{clean_id}.json"
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BackupSnapshot.from_dict(data)

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Lists all stored backups sorted by creation time descending."""
        results = []
        for file in sorted(self.backup_dir.glob("snapshot_*.json"), reverse=True):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "snapshot_id": data.get("snapshot_id", file.stem),
                    "created_at": data.get("created_at"),
                    "account_name": data.get("account_name"),
                    "item_count": len(data.get("items", [])),
                    "file_path": str(file),
                })
            except Exception:
                continue
        return results

    def restore_snapshot(self, snapshot: BackupSnapshot, provider: Any) -> List[Dict[str, Any]]:
        """Restores all items in the snapshot back to their original state using the provider."""
        return self._restore_item_list(snapshot.items, provider)

    def restore_items_by_id(self, snapshot: BackupSnapshot, item_ids: List[str], provider: Any) -> List[Dict[str, Any]]:
        """Restores only selected items matching given id or entry_id list."""
        id_set = set(item_ids)
        target_items = [i for i in snapshot.items if i.id in id_set or i.entry_id in id_set]
        return self._restore_item_list(target_items, provider)

    def _restore_item_list(self, items: List[BackupItemState], provider: Any) -> List[Dict[str, Any]]:
        results = []
        for item in items:
            try:
                provider.restore_item(
                    entry_id=item.entry_id,
                    store_id=item.store_id,
                    target_folder=item.folder_path,
                    is_read=item.is_read,
                    categories=item.categories,
                )
                results.append({
                    "id": item.id,
                    "entry_id": item.entry_id,
                    "subject": item.subject,
                    "success": True,
                    "message": f"Wiederhergestellt in '{item.folder_path}' (Gelesen: {item.is_read})",
                })
            except Exception as ex:
                results.append({
                    "id": item.id,
                    "entry_id": item.entry_id,
                    "subject": item.subject,
                    "success": False,
                    "message": f"Fehler bei Wiederherstellung: {str(ex)}",
                })
        return results
