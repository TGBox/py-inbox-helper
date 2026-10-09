"""In-memory mock provider for testing and demonstration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional
import uuid

from py_inbox_helper.models import EmailItem, ExecutionResult, PlannedAction, ensure_utc
from py_inbox_helper.provider.base import AccountInfo, BaseMailProvider, FolderInfo


class MockMailProvider(BaseMailProvider):
    """In-memory mock provider containing sample chaotic emails."""

    def __init__(self):
        self.accounts = [
            AccountInfo(
                id="acc-1",
                name="Hauptkonto (Office 365)",
                email_address="daniel@unternehmen.de",
                is_default=True,
            ),
            AccountInfo(
                id="acc-2",
                name="Gemeinsames Postfach (Support / Info)",
                email_address="support@unternehmen.de",
                is_default=False,
            ),
        ]

        self.folders: Dict[str, List[FolderInfo]] = {
            "acc-1": [
                FolderInfo(id="f-inbox", name="Posteingang", path="Posteingang", item_count=12, unread_count=9, is_inbox=True),
                FolderInfo(id="f-sent", name="Gesendete Elemente", path="Gesendete Elemente", item_count=4),
                FolderInfo(id="f-archive", name="Archiv", path="Archiv", item_count=20),
            ],
            "acc-2": [
                FolderInfo(id="f-inbox-2", name="Posteingang", path="Posteingang", item_count=5, unread_count=4, is_inbox=True),
            ]
        }

        self.items: Dict[str, EmailItem] = {}
        self._populate_sample_items()

    def _populate_sample_items(self):
        now = datetime.now(timezone.utc)
        samples = [
            # 1. Newsletter with 1-click unsubscribe
            EmailItem(
                id="mock-1",
                entry_id="EID-1",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Wöchentlicher Tech-Report: Die Trends der Woche",
                sender_name="Tech Digest",
                sender_email="newsletter@techdigest.io",
                received_time=now - timedelta(days=2),
                body_preview="Hallo Daniel, hier sind die Top-News der Woche...",
                is_read=False,
                folder_path="Posteingang",
                headers={
                    "List-Unsubscribe": "<mailto:unsub@techdigest.io>, <https://techdigest.io/unsub?id=123>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                },
            ),
            # 2. Marketing without 1-click
            EmailItem(
                id="mock-2",
                entry_id="EID-2",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="30% Rabatt auf alle Büroartikel - Nur heute!",
                sender_name="Office Supplies Online",
                sender_email="promo@officesupplies.de",
                received_time=now - timedelta(days=4),
                body_preview="Sichern Sie sich jetzt hochwertige Bürostühle und Zubehör...",
                is_read=False,
                folder_path="Posteingang",
                headers={
                    "List-Unsubscribe": "<https://officesupplies.de/newsletter/abmelden>",
                },
            ),
            # 3. Invoice / Finance
            EmailItem(
                id="mock-3",
                entry_id="EID-3",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Ihre Rechnung INV-2026-90812 von Cloud Services GmbH",
                sender_name="Cloud Services Buchhaltung",
                sender_email="rechnung@cloudservices.de",
                received_time=now - timedelta(days=5),
                body_preview="Sehr geehrter Kunde, im Anhang finden Sie die Rechnung für den Monat...",
                is_read=False,
                folder_path="Posteingang",
            ),
            # 4. System Notification / No-Reply
            EmailItem(
                id="mock-4",
                entry_id="EID-4",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Sicherheitsmeldung: Neuer Zugriff auf Microsoft 365",
                sender_name="Microsoft Security",
                sender_email="no-reply@microsoft.com",
                received_time=now - timedelta(days=1),
                body_preview="Ihr Konto wurde auf einem neuen Windows-Gerät angemeldet...",
                is_read=False,
                folder_path="Posteingang",
            ),
            # 5. Urgent / Important Action Required
            EmailItem(
                id="mock-5",
                entry_id="EID-5",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Dringend: Rückmeldung zum Projektvertrag bis morgen erbeten",
                sender_name="Dr. Weber",
                sender_email="m.weber@partner-kanzlei.de",
                received_time=now - timedelta(days=1),
                body_preview="Hallo Daniel, bitte prüfe den beiliegenden Entwurf kurzfristig...",
                is_read=False,
                importance="high",
                folder_path="Posteingang",
            ),
            # 6. Resubmission / Wiedervorlage
            EmailItem(
                id="mock-6",
                entry_id="EID-6",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Wiedervorlage: Nachfassen Kundenangebot Maier",
                sender_name="Vertriebsassistenz",
                sender_email="vertrieb@unternehmen.de",
                received_time=now - timedelta(days=15),
                body_preview="Erinnerung an das Angebot für Firma Maier bezüglich IT-Rollout...",
                is_read=True,
                folder_path="Posteingang",
            ),
            # 7. Old email for archiving (> 180 days)
            EmailItem(
                id="mock-7",
                entry_id="EID-7",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Abstimmung Weihnachtsfeier 2024",
                sender_name="Team Event",
                sender_email="events@unternehmen.de",
                received_time=now - timedelta(days=450),
                body_preview="Hier sind die Menüvorschläge für die Feier...",
                is_read=True,
                folder_path="Posteingang",
            ),
            # 8. Junk / Spam
            EmailItem(
                id="mock-8",
                entry_id="EID-8",
                store_id="acc-1",
                account_name="daniel@unternehmen.de",
                subject="Glückwunsch! Ihr Casino Gewinn wartet auf Auszahlung",
                sender_name="Lucky Win Lottery",
                sender_email="winner@jackpot-casino-free.com",
                received_time=now - timedelta(days=8),
                body_preview="Klicken Sie hier um Ihren Gewinn zu beanspruchen...",
                is_read=False,
                folder_path="Posteingang",
            ),
        ]

        for s in samples:
            self.items[s.entry_id] = s

    def list_accounts(self) -> List[AccountInfo]:
        return list(self.accounts)

    def list_folders(self, account_id: str) -> List[FolderInfo]:
        return list(self.folders.get(account_id, []))

    def fetch_emails(
        self,
        account_id: str,
        folder_paths: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        max_count: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[EmailItem]:
        matches = [
            item for item in self.items.values()
            if item.store_id == account_id and item.folder_path in folder_paths
        ]
        if date_from:
            df = ensure_utc(date_from)
            matches = [m for m in matches if ensure_utc(m.received_time) >= df]
        if date_to:
            dt = ensure_utc(date_to)
            matches = [m for m in matches if ensure_utc(m.received_time) <= dt]

        total = len(matches)
        results = []
        for i, item in enumerate(matches):
            if max_count and len(results) >= max_count:
                break
            results.append(item)
            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def get_item(self, entry_id: str, store_id: str) -> Optional[EmailItem]:
        return self.items.get(entry_id)

    def execute_action(self, action: PlannedAction, account_id: str) -> ExecutionResult:
        item = next((i for i in self.items.values() if i.id == action.email_id), None)
        if not item:
            return ExecutionResult(action=action, success=False, message="E-Mail nicht gefunden")

        if action.target_folder:
            item.folder_path = action.target_folder
        if action.mark_as_read:
            item.is_read = True
        elif action.mark_as_unread:
            item.is_read = False
        if action.add_category and action.add_category not in item.categories:
            item.categories.append(action.add_category)

        return ExecutionResult(
            action=action,
            success=True,
            is_dry_run=False,
            message="Erfolgreich ausgeführt in Mock-Postfach",
        )

    def restore_item(
        self,
        entry_id: str,
        store_id: str,
        target_folder: str,
        is_read: bool,
        categories: List[str],
    ) -> None:
        item = self.items.get(entry_id)
        if item:
            item.folder_path = target_folder
            item.is_read = is_read
            item.categories = list(categories)
