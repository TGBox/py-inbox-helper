"""Dialog for browsing, loading, importing, exporting, and managing saved analysis sessions."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.analysis_storage import AnalysisStorageManager
from py_inbox_helper.models import AnalysisSession
from py_inbox_helper.storage import format_bytes
from py_inbox_helper.ui.styles import CATEGORY_COLORS


class SavedAnalysesDialog(QDialog):
    """Dialog allowing users to inspect and restore previously saved analysis sessions.
    
    Supports both windowed and fullscreen modes (F11), instant search filtering,
    JSON file import/export, and session details inspection.
    """

    session_loaded = Signal(object)  # Emits AnalysisSession

    def __init__(
        self,
        storage_manager: AnalysisStorageManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint
        )
        self.storage_manager = storage_manager
        self.selected_session: Optional[AnalysisSession] = None
        self._sessions_data: List[Dict[str, Any]] = []
        self._filtered_data: List[Dict[str, Any]] = []

        self.setWindowTitle("Gespeicherte Analyse-Sitzungen verwalten && laden")
        self.resize(980, 680)

        self._init_ui()
        self._setup_shortcuts()
        self.reload_sessions()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Header Toolbar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        title_box = QVBoxLayout()
        title_lbl = QLabel("Gespeicherte E-Mail Analysen")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #38bdf8;")
        sub_lbl = QLabel("Wähle eine frühere Analyse aus, um direkt vor der Verarbeitung fortzufahren.")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        top_bar.addLayout(title_box)

        top_bar.addStretch()

        self.import_btn = QPushButton("Aus Datei importieren...")
        self.import_btn.setToolTip("Lädt eine gesicherte Analyse aus einer externen JSON-Datei")
        self.import_btn.clicked.connect(self._import_from_file)

        self.fullscreen_btn = QPushButton("Vollbild (F11)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        self.close_btn = QPushButton("Schließen (Esc)")
        self.close_btn.clicked.connect(self.reject)

        top_bar.addWidget(self.import_btn)
        top_bar.addWidget(self.fullscreen_btn)
        top_bar.addWidget(self.close_btn)
        layout.addLayout(top_bar)

        # 2. Search & Filter Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Analysen durchsuchen (Konto, Datum, Notizen)...")
        self.search_input.textChanged.connect(self._apply_filter)
        filter_bar.addWidget(QLabel("Suche:"))
        filter_bar.addWidget(self.search_input, 1)

        self.refresh_btn = QPushButton("Aktualisieren")
        self.refresh_btn.clicked.connect(self.reload_sessions)
        filter_bar.addWidget(self.refresh_btn)
        layout.addLayout(filter_bar)

        # 3. Main Splitter: Table & Details Panel
        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Erstellt am", "Postfach / Konto", "Notizen / Bezeichnung", "E-Mails", "Ungelesen", "Gesamtgröße"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 220)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 120)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.itemDoubleClicked.connect(lambda _: self._load_selected())
        splitter.addWidget(self.table)

        # Details Panel
        self.details_box = QFrame()
        self.details_box.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        d_layout = QVBoxLayout(self.details_box)
        d_layout.setContentsMargins(12, 10, 12, 10)
        d_layout.setSpacing(8)

        self.details_title = QLabel("Details der ausgewählten Analyse:")
        self.details_title.setStyleSheet("font-weight: 700; color: #f8fafc; font-size: 13px;")
        d_layout.addWidget(self.details_title)

        self.details_info = QLabel("Wähle eine Analyse-Sitzung in der Tabelle aus.")
        self.details_info.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.5;")
        self.details_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        d_layout.addWidget(self.details_info)

        # Category chips display
        self.category_chips_label = QLabel()
        self.category_chips_label.setStyleSheet("font-size: 11px;")
        d_layout.addWidget(self.category_chips_label)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        self.load_btn = QPushButton("Ausgewählte Analyse jetzt laden")
        self.load_btn.setObjectName("primaryBtn")
        self.load_btn.setEnabled(False)
        self.load_btn.setFixedHeight(36)
        self.load_btn.clicked.connect(self._load_selected)

        self.export_btn = QPushButton("In Datei exportieren...")
        self.export_btn.setEnabled(False)
        self.export_btn.setFixedHeight(36)
        self.export_btn.clicked.connect(self._export_selected)

        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setFixedHeight(36)
        self.delete_btn.setStyleSheet("QPushButton { background-color: #450a0a; border-color: #7f1d1d; color: #fca5a5; } QPushButton:hover { background-color: #7f1d1d; }")
        self.delete_btn.clicked.connect(self._delete_selected)

        actions_row.addWidget(self.load_btn, 2)
        actions_row.addWidget(self.export_btn, 1)
        actions_row.addWidget(self.delete_btn, 1)
        d_layout.addLayout(actions_row)

        splitter.addWidget(self.details_box)
        splitter.setSizes([380, 220])
        layout.addWidget(splitter, 1)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for window control."""
        self.f11_sc = QShortcut(QKeySequence(Qt.Key_F11), self)
        self.f11_sc.activated.connect(self.toggle_fullscreen)

        self.esc_sc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.esc_sc.activated.connect(self._handle_escape)

    def _handle_escape(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("Vollbild (F11)")
        else:
            self.reject()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("Vollbild (F11)")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("Fenstermodus (F11)")

    def reload_sessions(self):
        """Reloads stored analysis sessions from disk."""
        self._sessions_data = self.storage_manager.list_sessions()
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_input.text().strip().lower()
        if not query:
            self._filtered_data = list(self._sessions_data)
        else:
            self._filtered_data = [
                s for s in self._sessions_data
                if query in s.get("account_name", "").lower()
                or query in s.get("notes", "").lower()
                or query in s.get("session_id", "").lower()
                or query in s.get("created_at", "").lower()
            ]
        self._render_table()

    def _render_table(self):
        self.table.setRowCount(len(self._filtered_data))
        for row, s in enumerate(self._filtered_data):
            # Date
            created_str = s.get("created_at", "")
            try:
                dt = datetime.fromisoformat(created_str)
                display_date = dt.strftime("%d.%m.%Y %H:%M:%S")
            except Exception:
                display_date = created_str or "Unbekannt"

            d_item = QTableWidgetItem(display_date)
            d_item.setForeground(QColor("#38bdf8"))
            self.table.setItem(row, 0, d_item)

            # Account
            acc_item = QTableWidgetItem(s.get("account_name") or "(Standard)")
            acc_item.setForeground(QColor("#f8fafc"))
            self.table.setItem(row, 1, acc_item)

            # Notes
            notes_item = QTableWidgetItem(s.get("notes") or "—")
            notes_item.setForeground(QColor("#cbd5e1"))
            self.table.setItem(row, 2, notes_item)

            # Email count
            cnt_item = QTableWidgetItem(f"{s.get('item_count', 0)} Mails")
            cnt_item.setForeground(QColor("#f8fafc"))
            self.table.setItem(row, 3, cnt_item)

            # Unread
            unread_item = QTableWidgetItem(f"{s.get('unread_count', 0)} ungelesen")
            unread_item.setForeground(QColor("#ef4444") if s.get("unread_count", 0) > 0 else QColor("#10b981"))
            self.table.setItem(row, 4, unread_item)

            # Size
            size_str = format_bytes(s.get("total_size_bytes", 0))
            sz_item = QTableWidgetItem(size_str)
            sz_item.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, 5, sz_item)

        if self.table.rowCount() == 0:
            self._on_row_selected()
        else:
            self.table.selectRow(0)

    def _on_row_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.details_title.setText("Keine Analyse ausgewählt")
            self.details_info.setText("Wähle eine Analyse-Sitzung in der Tabelle aus.")
            self.category_chips_label.setText("")
            self.load_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        row = selected_rows[0].row()
        if row < len(self._filtered_data):
            session_meta = self._filtered_data[row]
            self.load_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

            acc = session_meta.get("account_name") or "(Standard-Konto)"
            created = session_meta.get("created_at")
            try:
                created_fmt = datetime.fromisoformat(created).strftime("%d.%m.%Y um %H:%M:%S Uhr")
            except Exception:
                created_fmt = created

            notes = session_meta.get("notes") or "(Keine Notizen)"
            items = session_meta.get("item_count", 0)
            size_str = format_bytes(session_meta.get("total_size_bytes", 0))
            unread = session_meta.get("unread_count", 0)

            self.details_title.setText(f"Sitzung: {session_meta.get('session_id')}")
            self.details_info.setText(
                f"<b>Postfach:</b> {acc} &nbsp;|&nbsp; <b>Erstellt:</b> {created_fmt}<br>"
                f"<b>Umfang:</b> {items} E-Mails ({size_str}) • {unread} ungelesen<br>"
                f"<b>Notizen / Bezeichnung:</b> {notes}"
            )

            # Render category breakdown
            cat_counts = session_meta.get("category_counts", {})
            chips = []
            for cat_name, count in cat_counts.items():
                cat_meta = CATEGORY_COLORS.get(cat_name, {"bg": "#1e293b", "fg": "#f8fafc"})
                chips.append(
                    f"<span style='background-color: {cat_meta['bg']}; color: {cat_meta['fg']}; padding: 2px 6px; border-radius: 4px; font-weight: 600;'>"
                    f"{cat_name}: {count}</span>"
                )
            if chips:
                self.category_chips_label.setText("<b>Kategorien:</b> " + " &nbsp; ".join(chips))
            else:
                self.category_chips_label.setText("")

    def _load_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_data):
            session_id = self._filtered_data[row]["session_id"]
            session = self.storage_manager.load_session(session_id)
            if session:
                self.selected_session = session
                self.session_loaded.emit(session)
                self.accept()
            else:
                QMessageBox.critical(self, "Fehler beim Laden", f"Die Sitzung '{session_id}' konnte nicht geladen werden.")

    def _export_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_data):
            session_id = self._filtered_data[row]["session_id"]
            default_name = f"{session_id}.json"
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "Analyse-Sitzung exportieren",
                default_name,
                "JSON-Dateien (*.json)",
            )
            if target_path:
                try:
                    self.storage_manager.export_session(session_id, Path(target_path))
                    QMessageBox.information(self, "Export erfolgreich", f"Die Analyse wurde erfolgreich exportiert nach:\n{target_path}")
                except Exception as ex:
                    QMessageBox.critical(self, "Export fehlgeschlagen", f"Fehler beim Exportieren:\n{ex}")

    def _import_from_file(self):
        src_path, _ = QFileDialog.getOpenFileName(
            self,
            "Analyse-Sitzung importieren",
            "",
            "JSON-Dateien (*.json)",
        )
        if src_path:
            try:
                session = self.storage_manager.import_session(Path(src_path))
                self.reload_sessions()
                QMessageBox.information(
                    self,
                    "Import erfolgreich",
                    f"Die Analyse '{session.session_id}' mit {len(session.emails)} E-Mails wurde erfolgreich importiert.",
                )
            except Exception as ex:
                QMessageBox.critical(self, "Import fehlgeschlagen", f"Fehler beim Importieren der Datei:\n{ex}")

    def _delete_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_data):
            session_id = self._filtered_data[row]["session_id"]
            confirm = QMessageBox.question(
                self,
                "Analyse löschen",
                f"Möchtest du die gespeicherte Analyse '{session_id}' wirklich löschen?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                if self.storage_manager.delete_session(session_id):
                    self.reload_sessions()
                else:
                    QMessageBox.critical(self, "Fehler", "Die Analyse konnte nicht gelöscht werden.")
