"""Scan configuration and account/folder selection tab."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.provider.base import AccountInfo, BaseMailProvider, FolderInfo


class ScanTab(QWidget):
    """Tab for configuring email accounts, target folders, date ranges, and initiating the scan."""

    start_scan_requested = Signal(str, list, object, object, object)  # account_id, folders, date_from, date_to, max_count
    cancel_scan_requested = Signal()

    def __init__(self, provider: BaseMailProvider, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.provider = provider
        self._accounts: List[AccountInfo] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Account Selection Box
        account_box = QGroupBox("1. Postfach && E-Mail-Konto auswählen")
        acc_layout = QVBoxLayout(account_box)

        acc_row = QHBoxLayout()
        acc_label = QLabel("Konto / Postfach:")
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        self.refresh_accounts_btn = QPushButton("Aktualisieren")
        self.refresh_accounts_btn.clicked.connect(self.reload_accounts)

        acc_row.addWidget(acc_label)
        acc_row.addWidget(self.account_combo, 1)
        acc_row.addWidget(self.refresh_accounts_btn)
        acc_layout.addLayout(acc_row)

        self.account_info_label = QLabel("Lädt Konten...")
        self.account_info_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        acc_layout.addWidget(self.account_info_label)
        layout.addWidget(account_box)

        # Resizable Splitter for Panels (Folders & Filters)
        panels_splitter = QSplitter(Qt.Vertical)

        # 2. Folder Selection Box
        folder_box = QGroupBox("2. Zu analysierende Ordner")
        folder_layout = QVBoxLayout(folder_box)

        folder_actions = QHBoxLayout()
        self.select_all_folders_btn = QPushButton("Alle auswählen")
        self.select_all_folders_btn.clicked.connect(self._select_all_folders)
        self.select_inbox_only_btn = QPushButton("Nur Posteingang")
        self.select_inbox_only_btn.clicked.connect(self._select_inbox_only)

        folder_actions.addWidget(self.select_inbox_only_btn)
        folder_actions.addWidget(self.select_all_folders_btn)
        folder_actions.addStretch()
        folder_layout.addLayout(folder_actions)

        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(110)
        folder_layout.addWidget(self.folder_list)
        panels_splitter.addWidget(folder_box)

        # 3. Filter Options
        filter_box = QGroupBox("3. Filter && Umfang")
        filter_form = QFormLayout(filter_box)

        self.time_filter_combo = QComboBox()
        self.time_filter_combo.addItems([
            "Alle E-Mails (ohne Zeitbegrenzung)",
            "Älter als 30 Tage",
            "Älter als 90 Tage",
            "Älter als 180 Tage (Empfohlen für Aufräumen)",
            "Älter als 1 Jahr (Archivierung)",
            "Benutzerdefinierter Zeitraum",
        ])
        self.time_filter_combo.currentIndexChanged.connect(self._on_time_filter_changed)
        filter_form.addRow("Zeitraum:", self.time_filter_combo)

        # Custom date row (initially hidden)
        self.custom_date_widget = QWidget()
        custom_date_layout = QHBoxLayout(self.custom_date_widget)
        custom_date_layout.setContentsMargins(0, 0, 0, 0)
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDate(datetime.now().date() - timedelta(days=365))
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDate(datetime.now().date())
        custom_date_layout.addWidget(QLabel("Von:"))
        custom_date_layout.addWidget(self.date_from_edit)
        custom_date_layout.addWidget(QLabel("Bis:"))
        custom_date_layout.addWidget(self.date_to_edit)
        self.custom_date_widget.setVisible(False)
        filter_form.addRow("Datum:", self.custom_date_widget)

        # Limit row
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100000)
        self.limit_spin.setValue(0)
        self.limit_spin.setSpecialValueText("Keine Begrenzung (Alle)")
        filter_form.addRow("Max. E-Mails:", self.limit_spin)

        panels_splitter.addWidget(filter_box)
        panels_splitter.setSizes([220, 180])
        layout.addWidget(panels_splitter)

        # 4. Action / Progress
        action_row = QHBoxLayout()
        self.start_btn = QPushButton("Postfach analysieren")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setFixedHeight(40)
        self.start_btn.clicked.connect(self._on_start_clicked)

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_scan_requested.emit)

        action_row.addWidget(self.start_btn, 2)
        action_row.addWidget(self.cancel_btn, 1)
        layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Bereit zum Scannen.")
        self.status_label.setStyleSheet("color: #94a3b8;")
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.reload_accounts()

    def reload_accounts(self, select_id: Optional[str] = None):
        """Loads accounts from the provider and optionally preselects a given account id."""
        self.account_combo.clear()
        try:
            self._accounts = self.provider.list_accounts()
            selected_idx = 0
            for idx, acc in enumerate(self._accounts):
                suffix = " (Standard)" if acc.is_default else ""
                self.account_combo.addItem(f"{acc.name}{suffix}", acc.id)
                if select_id and acc.id == select_id:
                    selected_idx = idx
            if self._accounts:
                self.account_combo.setCurrentIndex(selected_idx)
                self.account_info_label.setText(f"{len(self._accounts)} Konto/Postfächer gefunden.")
                self._load_folders_for_account(self._accounts[selected_idx].id)
            else:
                self.account_info_label.setText("Keine Konten gefunden.")
        except Exception as ex:
            self.account_info_label.setText(f"Fehler beim Laden der Konten: {ex}")

    def _on_account_changed(self, index: int):
        if index >= 0 and index < len(self._accounts):
            acc_id = self._accounts[index].id
            self._load_folders_for_account(acc_id)

    def _load_folders_for_account(self, account_id: str):
        self.folder_list.clear()
        try:
            folders = self.provider.list_folders(account_id)
            for f in folders:
                # Use f.name for decoded German characters display, keep f.path in data
                item = QListWidgetItem(f"{f.name} ({f.item_count} Mails)")
                item.setData(Qt.UserRole, f.path)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if f.is_inbox:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                self.folder_list.addItem(item)
        except Exception as ex:
            self.status_label.setText(f"Fehler beim Laden der Ordner: {ex}")

    def _select_all_folders(self):
        for i in range(self.folder_list.count()):
            self.folder_list.item(i).setCheckState(Qt.Checked)

    def _select_inbox_only(self):
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            path = item.data(Qt.UserRole)
            if "posteingang" in path.lower() or "inbox" in path.lower():
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _on_time_filter_changed(self, index: int):
        self.custom_date_widget.setVisible(index == 5)

    def _on_start_clicked(self):
        if self.account_combo.currentIndex() < 0:
            return
        account_id = self.account_combo.currentData()

        selected_folders = []
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_folders.append(item.data(Qt.UserRole))

        if not selected_folders:
            self.status_label.setText("Bitte mindestens einen Ordner zum Scannen auswählen!")
            return

        now = datetime.now(timezone.utc)
        filter_idx = self.time_filter_combo.currentIndex()
        date_from = None
        date_to = None

        if filter_idx == 1:
            date_to = now - timedelta(days=30)
        elif filter_idx == 2:
            date_to = now - timedelta(days=90)
        elif filter_idx == 3:
            date_to = now - timedelta(days=180)
        elif filter_idx == 4:
            date_to = now - timedelta(days=365)
        elif filter_idx == 5:
            # Custom
            df = self.date_from_edit.date().toPython()
            dt = self.date_to_edit.date().toPython()
            date_from = datetime(df.year, df.month, df.day, tzinfo=timezone.utc)
            date_to = datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=timezone.utc)

        max_count = self.limit_spin.value() or None

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Scan wird vorbereitet...")

        self.start_scan_requested.emit(account_id, selected_folders, date_from, date_to, max_count)

    def set_scan_in_progress(self, in_progress: bool):
        self.start_btn.setEnabled(not in_progress)
        self.cancel_btn.setEnabled(in_progress)
        self.progress_bar.setVisible(in_progress)

    def update_progress(self, current: int, total: int):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.status_label.setText(f"Fortschritt: {current} von {total} E-Mails ({percent}%)")

    def set_status_text(self, text: str):
        self.status_label.setText(text)
