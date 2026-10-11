"""Storage engine for saving and restoring analyzed email sessions."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from py_inbox_helper.models import AnalysisSession, EmailCategory, EmailItem

logger = logging.getLogger(__name__)


class AnalysisStorageManager:
    """Manages saving, listing, loading, exporting, and importing email analysis sessions."""

    def __init__(self, storage_dir: Optional[Path] = None):
        if storage_dir is None:
            self.storage_dir = Path.home() / ".py_inbox_helper" / "analyses"
        else:
            self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_session(
        self,
        account_id: str,
        account_name: str,
        emails: List[EmailItem],
        notes: str = "",
        custom_id: Optional[str] = None,
    ) -> AnalysisSession:
        """Saves current analyzed emails into a persistent JSON session file."""
        now = datetime.now(timezone.utc)
        if custom_id:
            clean_id = custom_id.replace(".json", "")
            session_id = clean_id
        else:
            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            short_id = uuid.uuid4().hex[:6]
            session_id = f"analysis_{timestamp_str}_{short_id}"

        session = AnalysisSession(
            session_id=session_id,
            created_at=now,
            account_id=account_id,
            account_name=account_name,
            emails=emails,
            notes=notes,
        )

        # Write session file atomically
        target_path = self.storage_dir / f"{session_id}.json"
        tmp_path = self.storage_dir / f"{session_id}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        tmp_path.replace(target_path)

        # Update latest pointer
        self._update_latest_pointer(session)

        logger.info("Saved analysis session '%s' with %d emails to %s", session_id, len(emails), target_path)
        return session

    def _update_latest_pointer(self, session: AnalysisSession) -> None:
        """Maintains latest_analysis.json for quick resumption."""
        try:
            latest_path = self.storage_dir / "latest_analysis.json"
            tmp_path = self.storage_dir / "latest_analysis.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
            tmp_path.replace(latest_path)
        except Exception as ex:
            logger.warning("Could not write latest analysis pointer: %s", ex)

    def load_session(self, session_id: str) -> Optional[AnalysisSession]:
        """Loads a session by session_id or filename."""
        clean_id = session_id.replace(".json", "")
        file_path = self.storage_dir / f"{clean_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AnalysisSession.from_dict(data)
        except Exception as ex:
            logger.error("Failed to load analysis session from %s: %s", file_path, ex)
            return None

    def load_latest_session(self) -> Optional[AnalysisSession]:
        """Loads the most recently saved session, if available."""
        latest_path = self.storage_dir / "latest_analysis.json"
        if latest_path.exists():
            try:
                with open(latest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AnalysisSession.from_dict(data)
            except Exception:
                pass

        # Fallback to the newest file in storage_dir
        sessions = self.list_sessions()
        if sessions:
            return self.load_session(sessions[0]["session_id"])
        return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lists all saved sessions with summary metadata sorted by date descending."""
        results: List[Dict[str, Any]] = []
        for file in sorted(self.storage_dir.glob("analysis_*.json"), reverse=True):
            if file.name == "latest_analysis.json":
                continue
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                emails_data = data.get("emails", [])
                total_bytes = sum(e.get("size_bytes", 0) for e in emails_data)
                unread_count = sum(1 for e in emails_data if not e.get("is_read", False))

                cat_counts: Dict[str, int] = {}
                for e in emails_data:
                    cat = e.get("assigned_category", "UNCLASSIFIED")
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1

                results.append({
                    "session_id": data.get("session_id", file.stem),
                    "created_at": data.get("created_at"),
                    "account_id": data.get("account_id", ""),
                    "account_name": data.get("account_name", ""),
                    "notes": data.get("notes", ""),
                    "item_count": len(emails_data),
                    "unread_count": unread_count,
                    "total_size_bytes": total_bytes,
                    "category_counts": cat_counts,
                    "file_path": str(file),
                })
            except Exception as ex:
                logger.debug("Skipping unreadable session file %s: %s", file, ex)
                continue

        # Sort descending by creation date
        results.sort(key=lambda s: s.get("created_at") or "", reverse=True)
        return results

    def delete_session(self, session_id: str) -> bool:
        """Deletes a saved session file."""
        clean_id = session_id.replace(".json", "")
        file_path = self.storage_dir / f"{clean_id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                # If deleted session was the latest, clear pointer
                latest_path = self.storage_dir / "latest_analysis.json"
                if latest_path.exists():
                    try:
                        with open(latest_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if data.get("session_id") == clean_id:
                            latest_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                return True
            except Exception as ex:
                logger.error("Failed to delete session %s: %s", file_path, ex)
                return False
        return False

    def export_session(self, session_id: str, target_path: Path) -> Path:
        """Exports a session to an arbitrary target file path."""
        session = self.load_session(session_id)
        if not session:
            raise FileNotFoundError(f"Analysis session '{session_id}' not found.")

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        return target

    def import_session(self, source_path: Path) -> AnalysisSession:
        """Imports an external JSON analysis session file and stores it locally."""
        src = Path(source_path)
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
        session = AnalysisSession.from_dict(data)

        # Save to local storage
        self.save_session(
            account_id=session.account_id,
            account_name=session.account_name,
            emails=session.emails,
            notes=session.notes or f"Importiert aus {src.name}",
            custom_id=session.session_id or f"imported_{src.stem}",
        )
        return session
