"""Background QThread workers for asynchronous non-blocking operations."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, List, Optional
from PySide6.QtCore import QThread, Signal

from py_inbox_helper.analyzer import EmailAnalyzer
from py_inbox_helper.backup import BackupManager
from py_inbox_helper.models import ActionPlan, EmailItem, ExecutionResult
from py_inbox_helper.provider.base import BaseMailProvider
from py_inbox_helper.unsubscribe import UnsubscribeManager


class ScanWorker(QThread):
    """Background worker for fetching and analyzing emails."""
    progress = Signal(int, int)  # current, total
    status_updated = Signal(str)
    finished = Signal(list)       # List[EmailItem]
    failed = Signal(str)

    def __init__(
        self,
        provider: BaseMailProvider,
        analyzer: EmailAnalyzer,
        account_id: str,
        folder_paths: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        max_count: Optional[int] = None,
    ):
        super().__init__()
        self.provider = provider
        self.analyzer = analyzer
        self.account_id = account_id
        self.folder_paths = folder_paths
        self.date_from = date_from
        self.date_to = date_to
        self.max_count = max_count
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.status_updated.emit("E-Mails werden aus Postfach geladen...")

            def progress_cb(current: int, total: int):
                if not self._is_cancelled:
                    self.progress.emit(current, total)

            emails = self.provider.fetch_emails(
                account_id=self.account_id,
                folder_paths=self.folder_paths,
                date_from=self.date_from,
                date_to=self.date_to,
                max_count=self.max_count,
                progress_callback=progress_cb,
            )

            if self._is_cancelled:
                self.status_updated.emit("Scan abgebrochen.")
                return

            self.status_updated.emit(f"{len(emails)} E-Mails geladen. Führe Analyse durch...")
            analyzed_emails = self.analyzer.analyze_batch(emails)

            self.status_updated.emit("Analyse abgeschlossen.")
            self.finished.emit(analyzed_emails)

        except Exception as ex:
            self.failed.emit(str(ex))


class ExecutionWorker(QThread):
    """Background worker that creates a backup snapshot and executes planned actions."""
    progress = Signal(int, int)  # current, total
    status_updated = Signal(str)
    item_finished = Signal(object)  # ExecutionResult
    finished = Signal(list, str)   # List[ExecutionResult], snapshot_id
    failed = Signal(str)

    def __init__(
        self,
        provider: BaseMailProvider,
        backup_manager: BackupManager,
        unsubscribe_manager: UnsubscribeManager,
        plan: ActionPlan,
        raw_emails: List[EmailItem],
    ):
        super().__init__()
        self.provider = provider
        self.backup_manager = backup_manager
        self.unsubscribe_manager = unsubscribe_manager
        self.plan = plan
        self.raw_emails = raw_emails
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            # 1. Mandatory Safety Backup Snapshot
            self.status_updated.emit("Sicherheitsschritt: Erstelle vollständiges Backup-Snapshot...")
            snapshot = self.backup_manager.create_snapshot(self.plan.account_name, self.raw_emails)
            saved_file = self.backup_manager.save_snapshot(snapshot)
            self.status_updated.emit(f"Wiederherstellungspunkt gesichert: {snapshot.snapshot_id}")

            # 2. Execute Actions
            enabled_actions = [a for a in self.plan.actions if a.is_enabled]
            total = len(enabled_actions)
            results: List[ExecutionResult] = []

            snapshot_items = {item.id: item for item in snapshot.items}
            emails_by_id = {e.id: e for e in self.raw_emails}
            unsubscribed_senders: set = set()
            unsaved_moves = 0

            try:
                for i, action in enumerate(enabled_actions):
                    if self._is_cancelled:
                        self.status_updated.emit("Ausführung abgebrochen.")
                        break

                    self.status_updated.emit(f"Verarbeite E-Mail {i + 1}/{total}: '{action.email_subject[:40]}...'")

                    # Perform mail operation (move, mark read, etc.)
                    res = self.provider.execute_action(action, self.plan.account_name)

                    # Remember where the item lives now. Moving can change its provider
                    # id, and without the new id a rollback could not find it again.
                    if res.new_folder:
                        state = snapshot_items.get(action.email_id)
                        if state is not None:
                            state.current_folder = res.new_folder
                            state.current_entry_id = res.new_entry_id
                            unsaved_moves += 1
                    if unsaved_moves >= 50:
                        self.backup_manager.save_snapshot(snapshot)
                        unsaved_moves = 0

                    # Optional unsubscribe operation (once per sender, not once per mail)
                    if action.unsubscribe and (action.unsubscribe_url or action.unsubscribe_mailto):
                        email_obj = emails_by_id.get(action.email_id)
                        if email_obj:
                            sender_key = (email_obj.sender_email or "").strip().lower() or (
                                action.unsubscribe_url or action.unsubscribe_mailto
                            )
                            if sender_key in unsubscribed_senders:
                                res.message += " | Abmeldung: bereits über eine andere E-Mail dieses Absenders ausgelöst"
                            else:
                                unsubscribed_senders.add(sender_key)
                                unsub_res = self.unsubscribe_manager.execute_unsubscribe(email_obj)
                                res.message += f" | Abmeldung: {unsub_res.message}"

                    results.append(res)
                    self.item_finished.emit(res)
                    self.progress.emit(i + 1, total)
            finally:
                # Always persist the new locations - also after a cancel or crash.
                self.backup_manager.save_snapshot(snapshot)
                self._close_provider()

            failed_count = sum(1 for r in results if not r.success)
            if failed_count:
                self.status_updated.emit(f"Ausführung abgeschlossen – {failed_count} von {len(results)} Aktionen fehlgeschlagen.")
            else:
                self.status_updated.emit("Ausführung abgeschlossen.")
            self.finished.emit(results, snapshot.snapshot_id)

        except Exception as ex:
            self.failed.emit(str(ex))

    def _close_provider(self) -> None:
        close = getattr(self.provider, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


class RestoreWorker(QThread):
    """Background worker for restoring a previous snapshot (full or granular)."""
    status_updated = Signal(str)
    finished = Signal(list)  # List[Dict[str, Any]]
    failed = Signal(str)

    def __init__(
        self,
        provider: BaseMailProvider,
        backup_manager: BackupManager,
        snapshot_id: str,
        item_ids: Optional[List[str]] = None,
    ):
        super().__init__()
        self.provider = provider
        self.backup_manager = backup_manager
        self.snapshot_id = snapshot_id
        self.item_ids = item_ids

    def run(self):
        try:
            self.status_updated.emit(f"Lade Snapshot '{self.snapshot_id}'...")
            snapshot = self.backup_manager.load_snapshot(self.snapshot_id)
            if not snapshot:
                self.failed.emit(f"Snapshot '{self.snapshot_id}' nicht gefunden.")
                return

            try:
                if self.item_ids:
                    self.status_updated.emit(f"Stelle {len(self.item_ids)} ausgewählte Elemente wieder her...")
                    results = self.backup_manager.restore_items_by_id(snapshot, self.item_ids, self.provider)
                else:
                    self.status_updated.emit(f"Stelle alle {len(snapshot.items)} Elemente wieder her...")
                    results = self.backup_manager.restore_snapshot(snapshot, self.provider)
            finally:
                close = getattr(self.provider, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:
                        pass

            failed_count = sum(1 for r in results if not r.get("success"))
            if failed_count:
                self.status_updated.emit(
                    f"Wiederherstellung abgeschlossen – {failed_count} von {len(results)} Elementen fehlgeschlagen."
                )
            else:
                self.status_updated.emit("Wiederherstellung (Rollback) erfolgreich abgeschlossen.")
            self.finished.emit(results)

        except Exception as ex:
            self.failed.emit(str(ex))
