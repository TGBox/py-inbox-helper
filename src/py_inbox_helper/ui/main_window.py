"""Main application window with navigation, fullscreen/windowed toggles, AI, and IMAP support."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.ai import AiClient, AiConfig
from py_inbox_helper.analyzer import EmailAnalyzer
from py_inbox_helper.backup import BackupManager
from py_inbox_helper.models import ActionPlan, EmailItem, ExecutionResult
from py_inbox_helper.planner import ActionPlanner, PlannerPresetConfig
from py_inbox_helper.provider.base import BaseMailProvider
from py_inbox_helper.provider.imap_provider import ImapMailProvider, ImapProfileManager
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.provider.outlook_provider import OutlookComProvider
from py_inbox_helper.storage import format_bytes
from py_inbox_helper.ui.settings_dialog import SettingsDialog
from py_inbox_helper.ui.styles import DARK_THEME_QSS
from py_inbox_helper.ui.tabs.analysis_tab import AnalysisTab
from py_inbox_helper.ui.tabs.backup_tab import BackupTab
from py_inbox_helper.ui.tabs.protocol_tab import ProtocolTab
from py_inbox_helper.ui.tabs.rules_tab import RulesTab
from py_inbox_helper.ui.tabs.scan_tab import ScanTab
from py_inbox_helper.ui.workers import ExecutionWorker, RestoreWorker, ScanWorker
from py_inbox_helper.unsubscribe import UnsubscribeManager


class MainWindow(QMainWindow):
    """Primary application window with windowed and fullscreen modes, AI, and IMAP support."""

    def __init__(self, provider: Optional[BaseMailProvider] = None):
        super().__init__()
        self.setWindowTitle("py-inbox-helper - E-Mail Postfach Assistent")
        self.resize(1200, 800)

        # Initialize core services
        self.imap_manager = ImapProfileManager()
        if provider is not None:
            self.provider = provider
        else:
            outlook_prov = OutlookComProvider()
            if outlook_prov.is_available():
                self.provider = outlook_prov
            else:
                self.provider = MockMailProvider()

        self.backup_manager = BackupManager()
        self.analyzer = EmailAnalyzer()
        self.ai_config = AiConfig()
        self.ai_client = AiClient(self.ai_config)

        self.preset_config = PlannerPresetConfig()
        self.planner = ActionPlanner(self.preset_config)
        self.unsubscribe_manager = UnsubscribeManager()

        # State
        self.current_emails: List[EmailItem] = []
        self.current_plan: Optional[ActionPlan] = None
        self.current_account_id: str = ""

        # Workers
        self._scan_worker: Optional[ScanWorker] = None
        self._exec_worker: Optional[ExecutionWorker] = None
        self._restore_worker: Optional[RestoreWorker] = None

        self._init_ui()
        self._setup_shortcuts()
        self.setStyleSheet(DARK_THEME_QSS)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Header Bar
        header = QFrame()
        header.setObjectName("headerBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        # Title
        title_box = QVBoxLayout()
        title_label = QLabel("py-inbox-helper")
        title_label.setObjectName("appTitle")
        sub_label = QLabel("Postfach analysieren, aufräumen und strukturieren")
        sub_label.setObjectName("appSubtitle")
        title_box.addWidget(title_label)
        title_box.addWidget(sub_label)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Provider / Account Selector
        prov_label = QLabel("Konto / Provider:")
        prov_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_mode_changed)
        header_layout.addWidget(prov_label)
        header_layout.addWidget(self.provider_combo)

        # Settings Button
        self.settings_btn = QPushButton("Einstellungen (KI, IMAP, VIP)")
        self.settings_btn.clicked.connect(self._open_settings)
        header_layout.addWidget(self.settings_btn)

        # Fullscreen Toggle Button (User Rule 4)
        self.fullscreen_btn = QPushButton("Vollbild (F11)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        header_layout.addWidget(self.fullscreen_btn)

        main_layout.addWidget(header)

        # 2. Main Tab Widget
        self.tabs = QTabWidget()
        self.scan_tab = ScanTab(self.provider)
        self.analysis_tab = AnalysisTab()
        self.analysis_tab.set_ai_client(self.ai_client)
        self.rules_tab = RulesTab(self.preset_config)
        self.protocol_tab = ProtocolTab()
        self.backup_tab = BackupTab(self.backup_manager)

        self.tabs.addTab(self.scan_tab, "1. Postfach && Scan")
        self.tabs.addTab(self.analysis_tab, "2. Analyse && Filter")
        self.tabs.addTab(self.rules_tab, "3. Regeln && Aktionen")
        self.tabs.addTab(self.protocol_tab, "4. Dry-Run && Protokoll")
        self.tabs.addTab(self.backup_tab, "5. Backup && Rollback")

        main_layout.addWidget(self.tabs)

        # 3. Bottom Global Status Bar
        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 6, 16, 6)
        status_layout.setSpacing(16)

        self.status_connection_lbl = QLabel("🟢 Bereit")
        self.status_connection_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        self.status_data_lbl = QLabel("Keine Daten geladen")
        self.status_data_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.status_ai_lbl = QLabel("KI: Deaktiviert")
        self.status_ai_lbl.setStyleSheet("color: #64748b; font-size: 11px;")

        status_layout.addWidget(self.status_connection_lbl)
        status_layout.addWidget(self.status_data_lbl)
        status_layout.addStretch()
        status_layout.addWidget(self.status_ai_lbl)

        main_layout.addWidget(status_bar)

        self._refresh_provider_combo()
        self._update_status_bar()

        # Wire Tab Signals
        self.scan_tab.start_scan_requested.connect(self._start_scan)
        self.scan_tab.cancel_scan_requested.connect(self._cancel_scan)

        self.analysis_tab.add_to_whitelist_requested.connect(self._add_to_whitelist)
        self.analysis_tab.ai_summarize_requested.connect(self._run_ai_summary)
        self.analysis_tab.restore_single_requested.connect(self._restore_single_from_latest)

        self.rules_tab.generate_plan_requested.connect(self._generate_plan_and_dry_run)
        self.protocol_tab.run_dry_run_requested.connect(self._generate_plan_and_dry_run)
        self.protocol_tab.apply_changes_requested.connect(self._start_execution)

        self.backup_tab.restore_requested.connect(self._start_restore_all)
        self.backup_tab.restore_items_requested.connect(self._start_restore_items)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts including F11, Esc, Ctrl+1..5, and Ctrl+F."""
        self.fullscreen_action = QAction(self)
        self.fullscreen_action.setShortcut(QKeySequence(Qt.Key_F11))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(self.fullscreen_action)

        self.esc_action = QAction(self)
        self.esc_action.setShortcut(QKeySequence(Qt.Key_Escape))
        self.esc_action.triggered.connect(self._exit_fullscreen_on_esc)
        self.addAction(self.esc_action)

        # Tab navigation shortcuts: Ctrl+1 to Ctrl+5
        for i in range(5):
            sc = QShortcut(QKeySequence(f"Ctrl+{i+1}"), self)
            sc.activated.connect(lambda idx=i: self.tabs.setCurrentIndex(idx))

        # Search focus shortcut: Ctrl+F
        sc_find = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_find.activated.connect(self._focus_search)

    def _focus_search(self):
        """Focuses the quick search input in AnalysisTab."""
        self.tabs.setCurrentIndex(1)
        self.analysis_tab.search_input.setFocus()
        self.analysis_tab.search_input.selectAll()

    def _update_status_bar(self):
        """Refreshes status indicators at the bottom bar."""
        # Connection / Provider
        if isinstance(self.provider, OutlookComProvider):
            self.status_connection_lbl.setText("🟢 Verbunden: Outlook (Desktop COM)")
            self.status_connection_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        elif isinstance(self.provider, ImapMailProvider):
            self.status_connection_lbl.setText("🟢 Verbunden: IMAP")
            self.status_connection_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        else:
            self.status_connection_lbl.setText("🔵 Verbunden: Demo (Mock-Modus)")
            self.status_connection_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")

        # Data stats
        if self.current_emails:
            total_bytes = sum(e.size_bytes for e in self.current_emails)
            unread_count = sum(1 for e in self.current_emails if not e.is_read)
            self.status_data_lbl.setText(
                f"{len(self.current_emails)} E-Mails geladen ({format_bytes(total_bytes)}) • {unread_count} ungelesen"
            )
        else:
            self.status_data_lbl.setText("Keine Daten geladen (Postfach noch nicht gescannt)")

        # AI Engine status
        if self.ai_config.provider != "disabled":
            model = self.ai_config.model_name or "Standard"
            self.status_ai_lbl.setText(f"✨ KI: Aktiv ({self.ai_config.provider.upper()} - {model})")
            self.status_ai_lbl.setStyleSheet("color: #a855f7; font-size: 11px; font-weight: 600;")
        else:
            self.status_ai_lbl.setText("KI: Deaktiviert (Lokale Heuristik)")
            self.status_ai_lbl.setStyleSheet("color: #64748b; font-size: 11px;")

    def toggle_fullscreen(self):
        """Toggles between Fullscreen mode and Windowed mode."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("Vollbild (F11)")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("Fenstermodus (F11)")

    def _exit_fullscreen_on_esc(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("Vollbild (F11)")

    def _refresh_provider_combo(self, select_profile_id: Optional[str] = None):
        """Populates header dropdown with configured accounts and providers."""
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()

        # 1. Outlook
        self.provider_combo.addItem("Microsoft Outlook (Desktop)", ("OUTLOOK", None))

        # 2. Configured IMAP profiles
        profiles = self.imap_manager.list_profiles()
        for p in profiles:
            display_name = f"IMAP: {p.account_name} ({p.username or p.host})"
            self.provider_combo.addItem(display_name, ("IMAP", p.profile_id))

        # 3. Add new IMAP option
        self.provider_combo.addItem("+ Neues IMAP-Konto einrichten...", ("ADD_IMAP", None))

        # 4. Demo Mock option
        self.provider_combo.addItem("Demo-Modus (Mock Postfach)", ("MOCK", None))

        # Determine index to select
        target_idx = 0
        if select_profile_id:
            for idx in range(self.provider_combo.count()):
                data = self.provider_combo.itemData(idx)
                if data and data[0] == "IMAP" and data[1] == select_profile_id:
                    target_idx = idx
                    break
        elif isinstance(self.provider, OutlookComProvider):
            target_idx = 0
        elif isinstance(self.provider, ImapMailProvider):
            found = False
            for idx in range(self.provider_combo.count()):
                data = self.provider_combo.itemData(idx)
                if data and data[0] == "IMAP":
                    target_idx = idx
                    found = True
                    break
            if not found:
                target_idx = self.provider_combo.count() - 1
        else:
            target_idx = self.provider_combo.count() - 1

        self.provider_combo.setCurrentIndex(target_idx)
        self.provider_combo.blockSignals(False)

    def _open_settings(self, initial_tab: int = 0):
        dialog = SettingsDialog(self.ai_config, self.analyzer, self.imap_manager, self, initial_tab=initial_tab)
        if dialog.exec():
            self.ai_client.config = self.ai_config
            self.analysis_tab.set_ai_client(self.ai_client)
            self._refresh_provider_combo()
            if isinstance(self.provider, ImapMailProvider):
                self.scan_tab.reload_accounts()
            if self.current_emails:
                self.analyzer.analyze_batch(self.current_emails)
                self.analysis_tab.set_emails(self.current_emails)
        else:
            self._refresh_provider_combo()
        self._update_status_bar()

    def _on_provider_mode_changed(self, index: int):
        data = self.provider_combo.currentData()
        if not data:
            return
        mode, profile_id = data

        if mode == "ADD_IMAP":
            self._open_settings(initial_tab=1)
            return

        if mode == "OUTLOOK":
            outlook = OutlookComProvider()
            if not outlook.is_available():
                QMessageBox.warning(
                    self,
                    "Outlook nicht verfügbar",
                    "Microsoft Outlook konnte über COM nicht erreicht werden.\n"
                    "Wechsel zurück zum vorherigen Modus.",
                )
                self._refresh_provider_combo()
                return
            self.provider = outlook
            self.scan_tab.provider = self.provider
            self.scan_tab.reload_accounts()
        elif mode == "IMAP":
            self.provider = ImapMailProvider(self.imap_manager)
            self.scan_tab.provider = self.provider
            self.scan_tab.reload_accounts(select_id=profile_id)
        else:
            self.provider = MockMailProvider()
            self.scan_tab.provider = self.provider
            self.scan_tab.reload_accounts()
        self._update_status_bar()

    # --- VIP Whitelist & AI Handlers ---
    def _add_to_whitelist(self, sender: str):
        if sender not in self.analyzer.config.whitelist_senders:
            self.analyzer.config.whitelist_senders.append(sender)
            if self.isVisible():
                QMessageBox.information(
                    self,
                    "VIP-Whitelist aktualisiert",
                    f"Absender '{sender}' wurde zur Whitelist hinzugefügt und ist nun vor Verschiebung/Löschung geschützt.",
                )
            if self.current_emails:
                self.analyzer.analyze_batch(self.current_emails)
                self.analysis_tab.set_emails(self.current_emails)

    def _run_ai_summary(self, email: EmailItem):
        summary = self.ai_client.summarize_email(email)
        self.analysis_tab.display_ai_summary(summary)

    # --- Scan Workflow ---
    def _start_scan(self, account_id: str, folders: List[str], date_from, date_to, max_count):
        self.current_account_id = account_id
        self._scan_worker = ScanWorker(
            provider=self.provider,
            analyzer=self.analyzer,
            account_id=account_id,
            folder_paths=folders,
            date_from=date_from,
            date_to=date_to,
            max_count=max_count,
        )
        self._scan_worker.progress.connect(self.scan_tab.update_progress)
        self._scan_worker.status_updated.connect(self.scan_tab.set_status_text)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _cancel_scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()
            self.scan_tab.set_scan_in_progress(False)

    def _on_scan_finished(self, emails: List[EmailItem]):
        self.current_emails = emails
        self.scan_tab.set_scan_in_progress(False)
        self.scan_tab.set_status_text(f"Scan erfolgreich: {len(emails)} E-Mails geladen und analysiert.")
        self.analysis_tab.set_emails(emails)
        self._update_status_bar()
        self.tabs.setCurrentIndex(1)

    def _on_scan_failed(self, error_msg: str):
        self.scan_tab.set_scan_in_progress(False)
        self.scan_tab.set_status_text(f"Scan fehlgeschlagen: {error_msg}")
        QMessageBox.critical(self, "Fehler beim Scannen", f"Ein Fehler ist aufgetreten:\n{error_msg}")

    # --- Plan & Dry Run ---
    def _generate_plan_and_dry_run(self):
        if not self.current_emails:
            QMessageBox.information(self, "Hinweis", "Bitte führe zuerst einen Scan durch.")
            return

        self.current_plan = self.planner.create_plan(self.current_account_id, self.current_emails)
        dry_run_results = self.planner.simulate_dry_run(self.current_plan)

        self.protocol_tab.set_simulation_results(self.current_plan, dry_run_results)
        self.tabs.setCurrentIndex(3)

    # --- Execution Workflow ---
    def _start_execution(self):
        if not self.current_plan or not self.current_emails:
            return

        self.tabs.setCurrentIndex(4)
        self.backup_tab.set_status_text("Ausführung wird gestartet...")
        self.backup_tab.append_log("--- Start der Postfach-Bereinigung ---")

        self._exec_worker = ExecutionWorker(
            provider=self.provider,
            backup_manager=self.backup_manager,
            unsubscribe_manager=self.unsubscribe_manager,
            plan=self.current_plan,
            raw_emails=self.current_emails,
        )
        self._exec_worker.progress.connect(self.backup_tab.set_execution_progress)
        self._exec_worker.status_updated.connect(self.backup_tab.set_status_text)
        self._exec_worker.item_finished.connect(lambda res: self.backup_tab.append_log(f"{res.action.email_subject[:30]}: {res.message}"))
        self._exec_worker.finished.connect(self._on_execution_finished)
        self._exec_worker.failed.connect(self._on_execution_failed)
        self._exec_worker.start()

    def _on_execution_finished(self, results: List[ExecutionResult], snapshot_id: str):
        self.backup_tab.append_log("--- Ausführung abgeschlossen! ---")
        self.backup_tab.reload_snapshots()
        QMessageBox.information(
            self,
            "Erfolgreich ausgeführt",
            f"Alle {len(results)} Aktionen wurden erfolgreich ausgeführt.\n"
            f"Wiederherstellungspunkt '{snapshot_id}' wurde gesichert.",
        )

    def _on_execution_failed(self, error_msg: str):
        self.backup_tab.append_log(f"FEHLER: {error_msg}")
        QMessageBox.critical(self, "Fehler bei der Ausführung", f"Ein Fehler ist aufgetreten:\n{error_msg}")

    # --- Restore / Rollback Workflow ---
    def _start_restore_all(self, snapshot_id: str):
        self._restore_worker = RestoreWorker(
            provider=self.provider,
            backup_manager=self.backup_manager,
            snapshot_id=snapshot_id,
            item_ids=None,
        )
        self._restore_worker.status_updated.connect(self.backup_tab.set_status_text)
        self._restore_worker.finished.connect(self._on_restore_finished)
        self._restore_worker.failed.connect(self._on_restore_failed)
        self._restore_worker.start()

    def _start_restore_items(self, snapshot_id: str, item_ids: List[str]):
        self._restore_worker = RestoreWorker(
            provider=self.provider,
            backup_manager=self.backup_manager,
            snapshot_id=snapshot_id,
            item_ids=item_ids,
        )
        self._restore_worker.status_updated.connect(self.backup_tab.set_status_text)
        self._restore_worker.finished.connect(self._on_restore_finished)
        self._restore_worker.failed.connect(self._on_restore_failed)
        self._restore_worker.start()

    def _restore_single_from_latest(self, email_id: str):
        snapshots = self.backup_manager.list_snapshots()
        if not snapshots:
            QMessageBox.information(self, "Kein Backup", "Es ist noch kein Wiederherstellungspunkt vorhanden.")
            return

        latest_id = snapshots[0]["snapshot_id"]
        self.tabs.setCurrentIndex(4)
        self._start_restore_items(latest_id, [email_id])

    def _on_restore_finished(self, results: List[dict]):
        self.backup_tab.append_log("--- Rollback erfolgreich abgeschlossen! ---")
        for r in results:
            self.backup_tab.append_log(f"{r['subject'][:30]}: {r['message']}")
        QMessageBox.information(
            self,
            "Rollback abgeschlossen",
            f"{len(results)} Elemente wurden erfolgreich wiederhergestellt.",
        )

    def _on_restore_failed(self, error_msg: str):
        self.backup_tab.append_log(f"FEHLER bei Rollback: {error_msg}")
        QMessageBox.critical(self, "Fehler bei Wiederherstellung", f"Ein Fehler ist aufgetreten:\n{error_msg}")
