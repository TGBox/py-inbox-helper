"""Settings dialog for AI configuration, IMAP account profiles, and VIP whitelist."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.ai import AiClient, AiConfig
from py_inbox_helper.analyzer import EmailAnalyzer
from py_inbox_helper.provider.imap_provider import ImapConfig, ImapProfileManager


class SettingsDialog(QDialog):
    """Configuration dialog for AI models, IMAP server profiles, and Whitelist rules."""

    def __init__(
        self,
        ai_config: AiConfig,
        analyzer: EmailAnalyzer,
        imap_manager: ImapProfileManager,
        parent: Optional[QWidget] = None,
        initial_tab: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen - KI, IMAP && Whitelist")
        self.resize(550, 480)
        self.ai_config = ai_config
        self.analyzer = analyzer
        self.imap_manager = imap_manager
        self.initial_tab = initial_tab
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # TAB 1: AI Configuration
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_form = QFormLayout()

        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItem("Lokales Ollama", "ollama")
        self.ai_provider_combo.addItem("OpenAI-kompatible Cloud API", "openai_compatible")
        self.ai_provider_combo.addItem("Deaktiviert", "disabled")
        self.ai_provider_combo.setCurrentIndex(
            0 if self.ai_config.provider == "ollama" else (1 if self.ai_config.provider == "openai_compatible" else 2)
        )
        ai_form.addRow("KI-Dienst:", self.ai_provider_combo)

        self.ai_endpoint_edit = QLineEdit(self.ai_config.endpoint_url)
        ai_form.addRow("API-Endpunkt URL:", self.ai_endpoint_edit)

        self.ai_model_edit = QLineEdit(self.ai_config.model_name)
        ai_form.addRow("Modellname:", self.ai_model_edit)

        self.ai_key_edit = QLineEdit(self.ai_config.api_key or "")
        self.ai_key_edit.setEchoMode(QLineEdit.Password)
        self.ai_key_edit.setPlaceholderText("Nur für Cloud-Anbieter erforderlich...")
        ai_form.addRow("API-Schlüssel (optional):", self.ai_key_edit)

        ai_layout.addLayout(ai_form)

        ai_test_row = QHBoxLayout()
        self.ai_test_btn = QPushButton("KI-Verbindung testen")
        self.ai_test_btn.clicked.connect(self._test_ai_connection)
        self.ai_status_label = QLabel("")
        ai_test_row.addWidget(self.ai_test_btn)
        ai_test_row.addWidget(self.ai_status_label, 1)
        ai_layout.addLayout(ai_test_row)
        ai_layout.addStretch()
        self.tabs.addTab(ai_tab, "KI / LLM (Ollama)")

        # TAB 2: IMAP Profiles
        imap_tab = QWidget()
        imap_layout = QVBoxLayout(imap_tab)

        self.imap_list = QListWidget()
        self._reload_imap_list()
        imap_layout.addWidget(QLabel("Gespeicherte IMAP-Postfächer:"))
        imap_layout.addWidget(self.imap_list)

        imap_form_box = QGroupBox("Neues IMAP-Konto hinzufügen")
        if_layout = QFormLayout(imap_form_box)

        self.template_combo = QComboBox()
        self.template_combo.addItems(["Benutzerdefiniert", "Gmail (imap.gmail.com)", "GMX (imap.gmx.net)", "Web.de (imap.web.de)"])
        self.template_combo.currentIndexChanged.connect(self._on_imap_template_changed)
        if_layout.addRow("Vorlage:", self.template_combo)

        self.imap_name_edit = QLineEdit()
        self.imap_name_edit.setPlaceholderText("z.B. Mein privates GMX Postfach")
        if_layout.addRow("Kontobezeichnung:", self.imap_name_edit)

        self.imap_host_edit = QLineEdit()
        if_layout.addRow("Server (Host):", self.imap_host_edit)

        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        if_layout.addRow("Port:", self.imap_port_spin)

        self.imap_user_edit = QLineEdit()
        if_layout.addRow("Benutzername / E-Mail:", self.imap_user_edit)

        self.imap_pass_edit = QLineEdit()
        self.imap_pass_edit.setEchoMode(QLineEdit.Password)
        if_layout.addRow("Passwort / App-Passwort:", self.imap_pass_edit)

        add_imap_btn = QPushButton("Konto speichern")
        add_imap_btn.clicked.connect(self._save_imap_profile)
        if_layout.addRow("", add_imap_btn)

        imap_layout.addWidget(imap_form_box)
        self.tabs.addTab(imap_tab, "IMAP-Konten")

        # TAB 3: VIP & Whitelist
        wl_tab = QWidget()
        wl_layout = QVBoxLayout(wl_tab)
        wl_layout.addWidget(QLabel(
            "Trage hier E-Mail-Adressen oder Domains ein, die niemals automatisch gelöscht, "
            "verschoben oder archiviert werden dürfen (eine Adresse/Domain pro Zeile, z.B. '@firma.de' oder 'chef@mail.de'):"
        ))

        self.whitelist_edit = QTextEdit()
        current_wl = "\n".join(self.analyzer.config.whitelist_senders)
        self.whitelist_edit.setText(current_wl)
        wl_layout.addWidget(self.whitelist_edit)
        self.tabs.addTab(wl_tab, "VIP && Whitelist")

        self.tabs.setCurrentIndex(self.initial_tab)
        layout.addWidget(self.tabs)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Speichern && Schließen")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save_all_and_close)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _test_ai_connection(self):
        prov = self.ai_provider_combo.currentData()
        endpoint = self.ai_endpoint_edit.text().strip()
        model = self.ai_model_edit.text().strip()
        key = self.ai_key_edit.text().strip() or None
        test_client = AiClient(AiConfig(provider=prov, endpoint_url=endpoint, model_name=model, api_key=key))

        is_avail, msg = test_client.check_availability()
        if is_avail:
            self.ai_status_label.setText(f"Erreichbar und einsatzbereit ({msg}).")
            self.ai_status_label.setStyleSheet("color: #10b981; font-weight: 600;")
        else:
            self.ai_status_label.setText(f"Nicht erreichbar: {msg}")
            self.ai_status_label.setStyleSheet("color: #ef4444; font-weight: 600;")

    def _on_imap_template_changed(self, idx: int):
        if idx == 1:  # Gmail
            self.imap_host_edit.setText("imap.gmail.com")
            self.imap_port_spin.setValue(993)
        elif idx == 2:  # GMX
            self.imap_host_edit.setText("imap.gmx.net")
            self.imap_port_spin.setValue(993)
        elif idx == 3:  # Web.de
            self.imap_host_edit.setText("imap.web.de")
            self.imap_port_spin.setValue(993)

    def _reload_imap_list(self):
        self.imap_list.clear()
        for p in self.imap_manager.list_profiles():
            self.imap_list.addItem(f"{p.account_name} ({p.username} @ {p.host}:{p.port})")

    def _save_imap_profile(self):
        name = self.imap_name_edit.text().strip() or "IMAP Postfach"
        host = self.imap_host_edit.text().strip()
        user = self.imap_user_edit.text().strip()
        pwd = self.imap_pass_edit.text()

        if not host or not user:
            QMessageBox.warning(self, "Fehlende Angaben", "Bitte mindestens Host und Benutzername angeben.")
            return

        import uuid
        profile = ImapConfig(
            profile_id=f"imap-{uuid.uuid4().hex[:6]}",
            account_name=name,
            host=host,
            port=self.imap_port_spin.value(),
            use_ssl=True,
            username=user,
            password=pwd,
        )
        self.imap_manager.save_profile(profile)
        self._reload_imap_list()
        self.imap_name_edit.clear()
        self.imap_host_edit.clear()
        self.imap_user_edit.clear()
        self.imap_pass_edit.clear()
        QMessageBox.information(self, "Konto gespeichert", f"Konto '{name}' wurde erfolgreich hinzugefügt.")

    def _save_all_and_close(self):
        # 1. AI Config
        self.ai_config.provider = self.ai_provider_combo.currentData()
        self.ai_config.endpoint_url = self.ai_endpoint_edit.text().strip()
        self.ai_config.model_name = self.ai_model_edit.text().strip()
        self.ai_config.api_key = self.ai_key_edit.text().strip() or None
        self.ai_config.save_to_path()

        # 2. Whitelist
        lines = [line.strip() for line in self.whitelist_edit.toPlainText().splitlines() if line.strip()]
        self.analyzer.config.whitelist_senders = lines

        self.accept()
