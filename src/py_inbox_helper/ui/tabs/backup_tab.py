"""Backup and Rollback management tab with full and granular restore options."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.backup import BackupManager
from py_inbox_helper.models import BackupSnapshot


class BackupTab(QWidget):
    """Tab displaying previous backups, live execution log, and full/granular restore."""

    restore_requested = Signal(str)  # snapshot_id
    restore_items_requested = Signal(str, list)  # snapshot_id, list_of_ids

    def __init__(self, backup_manager: BackupManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.backup_manager = backup_manager
        self._snapshots: List[Dict[str, Any]] = []
        self._loaded_snapshot: Optional[BackupSnapshot] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Outer Splitter for Live-Protokoll vs Backups
        main_splitter = QSplitter(Qt.Vertical)

        # 1. Live Execution Status Box
        exec_box = QGroupBox("Ausführungsstatus && Live-Protokoll")
        e_layout = QVBoxLayout(exec_box)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        e_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Keine aktive Ausführung.")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        e_layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(60)
        self.log_text.setPlaceholderText("Echtzeit-Protokoll der ausgeführten Aktionen...")
        e_layout.addWidget(self.log_text)
        main_splitter.addWidget(exec_box)

        # 2. Main Backups Splitter: Snapshot List & Snapshot Detail Items
        splitter = QSplitter(Qt.Vertical)

        # Snapshots Table Box
        snap_box = QGroupBox("Gespeicherte Wiederherstellungspunkte (Backups)")
        sb_layout = QVBoxLayout(snap_box)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Wähle ein Backup aus, um Details anzuzeigen oder wiederherzustellen:"))
        self.refresh_btn = QPushButton("Liste aktualisieren")
        self.refresh_btn.clicked.connect(self.reload_snapshots)
        header_row.addWidget(self.refresh_btn)
        sb_layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Snapshot-ID", "Erstellt am", "Konto", "Gesicherte E-Mails"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 140)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_snapshot_selected)
        sb_layout.addWidget(self.table)
        splitter.addWidget(snap_box)

        # Snapshot Items Granular Box
        items_box = QGroupBox("Enthaltene E-Mails im ausgewählten Backup (Granulares Rollback)")
        ib_layout = QVBoxLayout(items_box)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(4)
        self.items_table.setHorizontalHeaderLabels([
            "Auswahl", "Betreff", "Ursprünglicher Ordner", "Gelesen-Status"
        ])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.items_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.items_table.setColumnWidth(0, 60)
        self.items_table.setColumnWidth(1, 280)
        self.items_table.setColumnWidth(2, 180)
        self.items_table.setColumnWidth(3, 120)
        self.items_table.horizontalHeader().setStretchLastSection(True)

        ib_layout.addWidget(self.items_table)
        splitter.addWidget(items_box)

        main_splitter.addWidget(splitter)
        main_splitter.setSizes([130, 370])
        layout.addWidget(main_splitter)

        # Restore Action Buttons
        restore_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Alle markieren")
        self.select_all_btn.clicked.connect(self._select_all_items)

        self.restore_selected_btn = QPushButton("Nur markierte E-Mails wiederherstellen")
        self.restore_selected_btn.setObjectName("warningBtn")
        self.restore_selected_btn.clicked.connect(self._on_restore_selected_clicked)

        self.restore_all_btn = QPushButton("Gesamtes Backup vollständig wiederherstellen")
        self.restore_all_btn.setObjectName("warningBtn")
        self.restore_all_btn.clicked.connect(self._on_restore_all_clicked)

        restore_row.addWidget(self.select_all_btn)
        restore_row.addStretch()
        restore_row.addWidget(self.restore_selected_btn)
        restore_row.addWidget(self.restore_all_btn)
        ib_layout.addLayout(restore_row)

        splitter.addWidget(items_box)
        splitter.setSizes([180, 240])
        layout.addWidget(splitter)

        self.reload_snapshots()

    def reload_snapshots(self):
        self._snapshots = self.backup_manager.list_snapshots()
        self.table.setRowCount(len(self._snapshots))
        for row, s in enumerate(self._snapshots):
            self.table.setItem(row, 0, QTableWidgetItem(s["snapshot_id"]))
            self.table.setItem(row, 1, QTableWidgetItem(s.get("created_at", "-")[:19].replace("T", " ")))
            self.table.setItem(row, 2, QTableWidgetItem(s.get("account_name", "-")))
            self.table.setItem(row, 3, QTableWidgetItem(str(s.get("item_count", 0))))

        if self._snapshots:
            self.table.selectRow(0)

    def _on_snapshot_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.items_table.setRowCount(0)
            return

        row = selected_rows[0].row()
        snapshot_id = self._snapshots[row]["snapshot_id"]
        snapshot = self.backup_manager.load_snapshot(snapshot_id)
        self._loaded_snapshot = snapshot

        if not snapshot:
            self.items_table.setRowCount(0)
            return

        self.items_table.setRowCount(len(snapshot.items))
        for r, item in enumerate(snapshot.items):
            # Checkbox
            check = QCheckBox()
            check.setChecked(True)
            self.items_table.setCellWidget(r, 0, check)

            # Subject
            self.items_table.setItem(r, 1, QTableWidgetItem(item.subject))

            # Original folder
            self.items_table.setItem(r, 2, QTableWidgetItem(item.folder_path))

            # Read status
            self.items_table.setItem(r, 3, QTableWidgetItem("Gelesen" if item.is_read else "Ungelesen"))

    def _select_all_items(self):
        for r in range(self.items_table.rowCount()):
            cb: QCheckBox = self.items_table.cellWidget(r, 0)
            if cb:
                cb.setChecked(True)

    def append_log(self, text: str):
        self.log_text.append(text)

    def set_execution_progress(self, current: int, total: int):
        self.progress_bar.setVisible(True)
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.status_label.setText(f"Ausführung läuft: {current}/{total} ({percent}%)")

    def set_status_text(self, text: str):
        self.status_label.setText(text)

    def _on_restore_all_clicked(self):
        if not self._loaded_snapshot:
            QMessageBox.information(self, "Hinweis", "Bitte wähle zuerst ein Backup aus.")
            return

        snapshot_id = self._loaded_snapshot.snapshot_id
        reply = QMessageBox.warning(
            self,
            "Vollständiges Rollback bestätigen",
            f"Möchtest du das Postfach vollständig anhand des Backups '{snapshot_id}' wiederherstellen?\n\n"
            f"Alle {len(self._loaded_snapshot.items)} Elemente werden in ihren Original-Ordner zurückbewegt.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText("Vollständige Wiederherstellung läuft...")
            self.restore_requested.emit(snapshot_id)

    def _on_restore_selected_clicked(self):
        if not self._loaded_snapshot:
            QMessageBox.information(self, "Hinweis", "Bitte wähle zuerst ein Backup aus.")
            return

        selected_ids = []
        for r in range(self.items_table.rowCount()):
            cb: QCheckBox = self.items_table.cellWidget(r, 0)
            if cb and cb.isChecked():
                selected_ids.append(self._loaded_snapshot.items[r].id)

        if not selected_ids:
            QMessageBox.information(self, "Hinweis", "Es wurden keine E-Mails zum Wiederherstellen markiert.")
            return

        snapshot_id = self._loaded_snapshot.snapshot_id
        reply = QMessageBox.warning(
            self,
            "Granulares Rollback bestätigen",
            f"Möchtest du nur die {len(selected_ids)} markierten E-Mails aus dem Backup '{snapshot_id}' wiederherstellen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText(f"Stelle {len(selected_ids)} markierte E-Mails wieder her...")
            self.restore_items_requested.emit(snapshot_id, selected_ids)
