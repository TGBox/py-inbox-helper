"""Backup and Rollback management tab."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.backup import BackupManager


class BackupTab(QWidget):
    """Tab displaying previous backups, live execution log, and 1-click restore/rollback."""

    restore_requested = Signal(str)  # snapshot_id

    def __init__(self, backup_manager: BackupManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.backup_manager = backup_manager
        self._snapshots: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Live Execution Status Box
        exec_box = QGroupBox("Ausführungsstatus & Live-Protokoll")
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
        self.log_text.setMaximumHeight(140)
        self.log_text.setPlaceholderText("Echtzeit-Protokoll der ausgeführten Aktionen...")
        e_layout.addWidget(self.log_text)

        layout.addWidget(exec_box)

        # 2. Backups List Box
        backups_box = QGroupBox("Gespeicherte Wiederherstellungspunkte (Backups)")
        b_layout = QVBoxLayout(backups_box)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Wähle ein Backup aus, um den vorherigen Zustand vollständig wiederherzustellen:"))
        self.refresh_btn = QPushButton("Liste aktualisieren")
        self.refresh_btn.clicked.connect(self.reload_snapshots)
        header_row.addWidget(self.refresh_btn)
        b_layout.addLayout(header_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "Snapshot-ID", "Erstellt am", "Konto", "Gesicherte E-Mails"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        b_layout.addWidget(self.table)

        # Restore action
        restore_row = QHBoxLayout()
        self.restore_btn = QPushButton("Ausgewähltes Backup wiederherstellen (Rollback)")
        self.restore_btn.setObjectName("warningBtn")
        self.restore_btn.setFixedHeight(40)
        self.restore_btn.clicked.connect(self._on_restore_clicked)
        restore_row.addStretch()
        restore_row.addWidget(self.restore_btn)
        b_layout.addLayout(restore_row)

        layout.addWidget(backups_box)
        self.reload_snapshots()

    def reload_snapshots(self):
        self._snapshots = self.backup_manager.list_snapshots()
        self.table.setRowCount(len(self._snapshots))
        for row, s in enumerate(self._snapshots):
            self.table.setItem(row, 0, QTableWidgetItem(s["snapshot_id"]))
            self.table.setItem(row, 1, QTableWidgetItem(s.get("created_at", "-")[:19].replace("T", " ")))
            self.table.setItem(row, 2, QTableWidgetItem(s.get("account_name", "-")))
            self.table.setItem(row, 3, QTableWidgetItem(str(s.get("item_count", 0))))

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

    def _on_restore_clicked(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Hinweis", "Bitte wähle zuerst ein Backup aus der Liste aus.")
            return

        row = selected_rows[0].row()
        snapshot_id = self._snapshots[row]["snapshot_id"]

        reply = QMessageBox.warning(
            self,
            "Wiederherstellung (Rollback) bestätigen",
            f"Möchtest du das Postfach anhand des Backups '{snapshot_id}' wiederherstellen?\n\n"
            "Alle verschobenen E-Mails werden zurück in ihre Ursprungsordner bewegt und die "
            "früheren Markierungen werden wiederhergestellt.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText("Wiederherstellung wird durchgeführt...")
            self.restore_requested.emit(snapshot_id)
