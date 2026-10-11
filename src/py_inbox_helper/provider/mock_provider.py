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
                body_preview="Hallo Daniel, hier sind die Top-News der Woche: Neue Entwicklungen in Python, Cloud-Infrastruktur und KI-Tools...",
                body_text=(
                    "Hallo Daniel,\n\n"
                    "hier sind die spannendsten Entwicklungen aus der Tech-Welt dieser Woche:\n\n"
                    "1. Python 3.14 und PySide6 Performance-Updates: Bis zu 20% schnellere UI-Zyklen.\n"
                    "2. Moderne Cloud-Orchestrierung und Multi-Region-Strategien.\n"
                    "3. Open-Source LLMs für lokale Entwicklungs-Workflows im Praxistest.\n\n"
                    "Den vollständigen Report kannst du jederzeit online abrufen.\n\n"
                    "Viele Grüße,\nDein Tech Digest Redaktionsteam"
                ),
                body_html=(
                    "<h3>Tech Digest - Ausgabe #142</h3>"
                    "<p>Hallo Daniel,</p>"
                    "<p>hier sind die spannendsten Entwicklungen aus der Tech-Welt dieser Woche:</p>"
                    "<ul>"
                    "<li><b>Python & PySide6:</b> Neue Benchmarks für reaktive Desktop-UIs.</li>"
                    "<li><b>Cloud-Architektur:</b> Effiziente Multi-Tenant Postfachverwaltung.</li>"
                    "<li><b>Lokale KI-Modelle:</b> Offline-Zusammenfassungen ohne Datenschutzrisiken.</li>"
                    "</ul>"
                    "<p>Viel Spaß beim Lesen!<br><i>Dein Tech Digest Team</i></p>"
                ),
                is_read=False,
                folder_path="Posteingang",
                size_bytes=42500,
                headers={
                    "List-Unsubscribe": "<mailto:unsub@techdigest.io>, <https://techdigest.io/unsub?id=123>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                    "From": "Tech Digest <newsletter@techdigest.io>",
                    "To": "daniel@unternehmen.de",
                    "Subject": "Wöchentlicher Tech-Report: Die Trends der Woche",
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
                body_text=(
                    "Guten Tag,\n\n"
                    "sparen Sie heute bis zu 30% auf ausgewählte Büroausstattung und ergonomische Arbeitsplätze!\n"
                    "Gutscheincode: BUERO2026\n\n"
                    "Gültig bis Mitternacht.\n\n"
                    "Ihr Office Supplies Team"
                ),
                body_html=(
                    "<h2>Exklusives Tagesangebot!</h2>"
                    "<p>Guten Tag,</p>"
                    "<p>sparen Sie heute bis zu <b>30% Rabatt</b> auf ergonomische Bürostühle, Schreibtische und Zubehör.</p>"
                    "<p style='color: #38bdf8;'>Gutscheincode: <b>BUERO2026</b></p>"
                    "<p>Gültig bis heute 23:59 Uhr.</p>"
                ),
                is_read=False,
                folder_path="Posteingang",
                size_bytes=89000,
                headers={
                    "List-Unsubscribe": "<https://officesupplies.de/newsletter/abmelden>",
                    "From": "Office Supplies Online <promo@officesupplies.de>",
                    "To": "daniel@unternehmen.de",
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
                body_text=(
                    "Sehr geehrter Kunde,\n\n"
                    "anbei erhalten Sie Ihre Rechnung INV-2026-90812 für den Abrechnungszeitraum September 2026.\n"
                    "Rechnungsbetrag: 149,00 EUR (netto)\n"
                    "Zahlungsziel: 14 Tage\n\n"
                    "Bei Fragen steht Ihnen unser Support gern zur Verfügung.\n\n"
                    "Mit freundlichen Grüßen,\nCloud Services Buchhaltung"
                ),
                body_html=(
                    "<h3>Rechnung INV-2026-90812</h3>"
                    "<p>Sehr geehrter Kunde,</p>"
                    "<p>vielen Dank für Ihr Vertrauen. Anbei finden Sie Ihre Abrechnung:</p>"
                    "<table border='1' cellpadding='6' style='border-collapse: collapse;'>"
                    "<tr><th>Position</th><th>Betrag</th></tr>"
                    "<tr><td>Cloud Hosting Enterprise</td><td>149,00 EUR</td></tr>"
                    "</table>"
                    "<p>Zahlbar innerhalb von 14 Tagen ohne Abzug.</p>"
                ),
                is_read=False,
                folder_path="Posteingang",
                size_bytes=245000,
                headers={
                    "From": "Cloud Services Buchhaltung <rechnung@cloudservices.de>",
                    "To": "daniel@unternehmen.de",
                },
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
                body_text=(
                    "Sicherheitswarnung für Ihr Microsoft-Konto:\n\n"
                    "Wir haben eine neue Anmeldung auf einem Windows-PC aus Deutschland festgestellt.\n"
                    "Zeitpunkt: Gestern, 18:42 Uhr UTC\n"
                    "IP-Adresse: 84.112.55.10\n\n"
                    "Wenn Sie dies waren, müssen Sie nichts unternehmen.\n"
                    "Falls nicht, überprüfen Sie umgehend Ihre Sicherheitsaktivitäten."
                ),
                body_html=(
                    "<h3>Microsoft Sicherheitsbenachrichtigung</h3>"
                    "<p>Wir haben eine neue Anmeldung an Ihrem Microsoft 365 Konto festgestellt:</p>"
                    "<p><b>Gerät:</b> Windows 11 Desktop<br>"
                    "<b>Standort:</b> Deutschland<br>"
                    "<b>IP:</b> 84.112.55.10</p>"
                    "<p>Wenn Sie dies waren, können Sie diese E-Mail ignorieren.</p>"
                ),
                is_read=False,
                folder_path="Posteingang",
                size_bytes=18400,
                headers={
                    "From": "Microsoft Security <no-reply@microsoft.com>",
                    "To": "daniel@unternehmen.de",
                },
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
                body_text=(
                    "Hallo Daniel,\n\n"
                    "bitte prüfe den beiliegenden finalen Vertragsentwurf bezüglich des IT-Projekts kurzfristig.\n"
                    "Die Gegenseite benötigt unsere Freigabe spätestens bis morgen, 12:00 Uhr.\n\n"
                    "Lass uns andernfalls heute Nachmittag kurz telefonieren.\n\n"
                    "Beste Grüße,\nDr. Michael Weber\nPartner-Kanzlei Rechtsanwälte"
                ),
                body_html=(
                    "<p>Hallo Daniel,</p>"
                    "<p>bitte prüfe den beiliegenden <b>finalen Vertragsentwurf</b> bezüglich des IT-Projekts kurzfristig.</p>"
                    "<p style='color: #ef4444;'><b>Frist: Morgen, 12:00 Uhr</b></p>"
                    "<p>Lass uns andernfalls kurz abstimmen.</p>"
                    "<p>Beste Grüße,<br><b>Dr. Michael Weber</b><br>Partner-Kanzlei Rechtsanwälte</p>"
                ),
                is_read=False,
                importance="high",
                folder_path="Posteingang",
                size_bytes=520000,
                headers={
                    "From": "Dr. Weber <m.weber@partner-kanzlei.de>",
                    "To": "daniel@unternehmen.de",
                    "Importance": "High",
                },
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
                body_text=(
                    "Hallo Team,\n\n"
                    "automatische Wiedervorlage: Bitte bei Firma Maier nachfassen, wie der Status "
                    "des Angebots vom 15. September ist.\n\n"
                    "Ansprechpartner: Herr Maier (GF)\n"
                    "Volumen: 45.000 EUR\n\n"
                    "Danke & Gruß,\nVertriebsassistenz"
                ),
                body_html=(
                    "<h3>Wiedervorlage / Follow-up</h3>"
                    "<p>Automatische Wiedervorlage für Kundenangebot <b>Firma Maier</b>.</p>"
                    "<p>Bitte Status ermitteln und nächste Schritte festhalten.</p>"
                ),
                is_read=True,
                folder_path="Posteingang",
                size_bytes=14200,
                headers={
                    "From": "Vertriebsassistenz <vertrieb@unternehmen.de>",
                    "To": "daniel@unternehmen.de",
                },
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
                body_text=(
                    "Liebe Kolleginnen und Kollegen,\n\n"
                    "hier sind die Menüvorschläge für unsere damalige Jahresabschlussfeier.\n"
                    "Vielen Dank an alle, die abgestimmt haben!\n\n"
                    "Euer Event-Team"
                ),
                body_html=(
                    "<p>Liebe Kolleginnen und Kollegen,</p>"
                    "<p>hier sind die archivierten Menüoptionen der Weihnachtsfeier 2024.</p>"
                ),
                is_read=True,
                folder_path="Posteingang",
                size_bytes=18500000,
                headers={
                    "From": "Team Event <events@unternehmen.de>",
                    "To": "daniel@unternehmen.de",
                },
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
                body_text=(
                    "Sie wurden als Gewinner von 5.000 EUR ausgewählt!\n\n"
                    "Klicken Sie sofort auf den Link unten, um Ihren Gewinn innerhalb von 24 Stunden zu beanspruchen.\n"
                    "http://suspicious-lottery-claim.com/claim?token=xyz\n\n"
                    "Ihr Lottery Team"
                ),
                body_html=(
                    "<h2 style='color: red;'>HERZLICHEN GLÜCKWUNSCH!</h2>"
                    "<p>Ihr Bargeldgewinn wartet auf Sie.</p>"
                ),
                is_read=False,
                folder_path="Posteingang",
                size_bytes=9400,
                headers={
                    "From": "Lucky Win Lottery <winner@jackpot-casino-free.com>",
                    "To": "daniel@unternehmen.de",
                },
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
