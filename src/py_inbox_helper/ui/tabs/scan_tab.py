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
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        # Main 2-Column Splitter (Left: Account & Folders, Right: Filters & Action Card)
        self.splitter = QSplitter(Qt.Horizontal)
        main_splitter = self.splitter

        # --- LEFT COLUMN: Account & Folders ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # 1. Account Selection Box
        account_box = QGroupBox("1. Postfach && E-Mail-Konto auswählen")
        acc_layout = QVBoxLayout(account_box)
        acc_layout.setSpacing(8)

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
        left_layout.addWidget(account_box)

        # 2. Folder Selection Box
        folder_box = QGroupBox("2. Zu analysierende Ordner")
        folder_layout = QVBoxLayout(folder_box)
        folder_layout.setSpacing(8)

        folder_actions = QHBoxLayout()
        self.select_inbox_only_btn = QPushButton("Nur Posteingang")
        self.select_inbox_only_btn.clicked.connect(self._select_inbox_only)
        self.select_all_folders_btn = QPushButton("Alle auswählen")
        self.select_all_folders_btn.clicked.connect(self._select_all_folders)
        self.deselect_all_btn = QPushButton("Keine")
        self.deselect_all_btn.clicked.connect(self._deselect_all_folders)

        folder_actions.addWidget(self.select_inbox_only_btn)
        folder_actions.addWidget(self.select_all_folders_btn)
        folder_actions.addWidget(self.deselect_all_btn)
        folder_actions.addStretch()
        folder_layout.addLayout(folder_actions)

        self.folder_list = QListWidget()
        self.folder_list.itemChanged.connect(self._update_folder_selection_stats)
        folder_layout.addWidget(self.folder_list)

        self.folder_stats_label = QLabel("Keine Ordner geladen.")
        self.folder_stats_label.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 500;")
        folder_layout.addWidget(self.folder_stats_label)

        left_layout.addWidget(folder_box, 1)
        main_splitter.addWidget(left_widget)

        # --- RIGHT COLUMN: Filter Options & Action Card ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # 3. Filter Options
        filter_box = QGroupBox("3. Filter && Analyse-Umfang")
        filter_form = QFormLayout(filter_box)
        filter_form.setSpacing(10)

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

        # Limit row with quick pills
        limit_container = QWidget()
        limit_layout = QVBoxLayout(limit_container)
        limit_layout.setContentsMargins(0, 0, 0, 0)
        limit_layout.setSpacing(6)

        limit_subrow = QHBoxLayout()
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100000)
        self.limit_spin.setValue(0)
        self.limit_spin.setSpecialValueText("Keine Begrenzung (Alle)")
        limit_subrow.addWidget(self.limit_spin, 1)

        self.pill_500 = QPushButton("500")
        self.pill_500.setFixedWidth(50)
        self.pill_500.clicked.connect(lambda: self.limit_spin.setValue(500))
        self.pill_1000 = QPushButton("1.000")
        self.pill_1000.setFixedWidth(60)
        self.pill_1000.clicked.connect(lambda: self.limit_spin.setValue(1000))
        self.pill_all = QPushButton("Alle")
        self.pill_all.setFixedWidth(50)
        self.pill_all.clicked.connect(lambda: self.limit_spin.setValue(0))

        limit_subrow.addWidget(self.pill_500)
        limit_subrow.addWidget(self.pill_1000)
        limit_subrow.addWidget(self.pill_all)
        limit_layout.addLayout(limit_subrow)

        filter_form.addRow("Max. E-Mails:", limit_container)
        right_layout.addWidget(filter_box)

        # 4. Action & Progress Box
        action_box = QGroupBox("4. Analyse ausführen")
        act_layout = QVBoxLayout(action_box)
        act_layout.setSpacing(10)

        info_hint = QLabel(
            "Hinweis: Der Analyse-Scan liest ausschließlich E-Mail-Metadaten.\n"
            "Es werden in diesem Schritt keinerlei Daten gelöscht oder verschoben."
        )
        info_hint.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.4;")
        act_layout.addWidget(info_hint)

        action_row = QHBoxLayout()
        self.start_btn = QPushButton("Postfach analysieren")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setFixedHeight(42)
        self.start_btn.clicked.connect(self._on_start_clicked)

        self.cancel_btn = QPushButton("Abbrechen")
        self.cancel_btn.setFixedHeight(42)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_scan_requested.emit)

        action_row.addWidget(self.start_btn, 2)
        action_row.addWidget(self.cancel_btn, 1)
        act_layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        act_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Bereit zum Scannen.")
        self.status_label.setStyleSheet("color: #38bdf8; font-weight: 500;")
        act_layout.addWidget(self.status_label)

        right_layout.addWidget(action_box)
        right_layout.addStretch()

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([380, 420])
        layout.addWidget(main_splitter)

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
        self._update_folder_selection_stats()

    def _select_all_folders(self):
        self.folder_list.blockSignals(True)
        for i in range(self.folder_list.count()):
            self.folder_list.item(i).setCheckState(Qt.Checked)
        self.folder_list.blockSignals(False)
        self._update_folder_selection_stats()

    def _deselect_all_folders(self):
        self.folder_list.blockSignals(True)
        for i in range(self.folder_list.count()):
            self.folder_list.item(i).setCheckState(Qt.Unchecked)
        self.folder_list.blockSignals(False)
        self._update_folder_selection_stats()

    def _select_inbox_only(self):
        self.folder_list.blockSignals(True)
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            path = item.data(Qt.UserRole)
            if "posteingang" in path.lower() or "inbox" in path.lower():
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
        self.folder_list.blockSignals(False)
        self._update_folder_selection_stats()

    def _update_folder_selection_stats(self):
        total = self.folder_list.count()
        selected = sum(1 for i in range(total) if self.folder_list.item(i).checkState() == Qt.Checked)
        if total == 0:
            self.folder_stats_label.setText("Keine Ordner geladen.")
        elif selected == 0:
            self.folder_stats_label.setText(f"0 von {total} Ordnern ausgewählt (Bitte mindestens 1 wählen).")
            self.folder_stats_label.setStyleSheet("color: #f59e0b; font-size: 12px; font-weight: 500;")
        else:
            self.folder_stats_label.setText(f"✓ {selected} von {total} Ordnern für die Analyse ausgewählt.")
            self.folder_stats_label.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: 500;")

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
