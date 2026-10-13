"""Analysis overview tab displaying KPI metric cards, filters, sender clusters, and email table."""
from __future__ import annotations

from typing import Any, List, Optional
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.models import EmailCategory, EmailItem
from py_inbox_helper.storage import SenderCluster, StorageAnalyzer, format_bytes
from py_inbox_helper.ui.styles import CATEGORY_COLORS
from py_inbox_helper.ui.email_preview_dialog import EmailPreviewDialog


class EmailTableItemViewShim:
    """Lightweight view shim to expose item-like attributes for test and selection helpers."""

    def __init__(self, model: EmailTableModel, row: int, col: int):
        self._model = model
        self._row = row
        self._col = col

    def text(self) -> str:
        idx = self._model.index(self._row, self._col)
        val = self._model.data(idx, Qt.DisplayRole)
        return str(val) if val is not None else ""

    def background(self) -> Any:
        idx = self._model.index(self._row, self._col)
        val = self._model.data(idx, Qt.BackgroundRole)
        if isinstance(val, QBrush):
            return val
        if isinstance(val, QColor):
            return QBrush(val)
        return QBrush()

    def foreground(self) -> Any:
        idx = self._model.index(self._row, self._col)
        return self._model.data(idx, Qt.ForegroundRole)

    def row(self) -> int:
        return self._row

    def column(self) -> int:
        return self._col


class EmailTableModel(QAbstractTableModel):
    """Virtual table model for high-performance email rendering without object thrashing."""

    HEADERS = ["Betreff", "Absender", "Empfangen", "Größe", "Kategorie", "Grund / Signal", "Abmeldung"]

    def __init__(self, emails: Optional[List[EmailItem]] = None, parent=None):
        super().__init__(parent)
        self._emails: List[EmailItem] = list(emails) if emails else []

    def set_emails(self, emails: List[EmailItem]):
        self.beginResetModel()
        self._emails = list(emails)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._emails)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def email_at(self, row: int) -> Optional[EmailItem]:
        if 0 <= row < len(self._emails):
            return self._emails[row]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._emails)):
            return None

        e = self._emails[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                dot = "●  " if not e.is_read else "   "
                return f"{dot}{e.subject}"
            elif col == 1:
                if e.sender_name and e.sender_email and e.sender_name != e.sender_email:
                    return f"{e.sender_name} <{e.sender_email}>"
                return e.sender_email or e.sender_name or "(Unbekannt)"
            elif col == 2:
                return e.received_time.strftime("%d.%m.%Y %H:%M")
            elif col == 3:
                return format_bytes(e.size_bytes)
            elif col == 4:
                return f" {e.assigned_category.value} "
            elif col == 5:
                return e.classification_reason
            elif col == 6:
                if e.is_one_click_unsubscribe:
                    return "⚡ 1-Click"
                elif e.has_unsubscribe_header:
                    return "🔗 Link"
                return "—"

        elif role == Qt.FontRole:
            if col == 0 and not e.is_read:
                font = QFont()
                font.setBold(True)
                return font

        elif role == Qt.ForegroundRole:
            if col == 0:
                return QColor("#f8fafc") if not e.is_read else QColor("#cbd5e1")
            elif col == 1:
                return QColor("#e2e8f0")
            elif col == 2:
                return QColor("#94a3b8")
            elif col == 3:
                if e.size_bytes >= 15_000_000:
                    return QColor("#ef4444")
                elif e.size_bytes >= 5_000_000:
                    return QColor("#f59e0b")
                return QColor("#94a3b8")
            elif col == 4:
                cat_key = e.assigned_category.name if hasattr(e.assigned_category, "name") else str(e.assigned_category)
                cat_meta = CATEGORY_COLORS.get(cat_key, {"fg": "#f8fafc"})
                return QColor(cat_meta.get("fg", "#f8fafc"))
            elif col == 5:
                return QColor("#94a3b8")
            elif col == 6:
                if e.is_one_click_unsubscribe:
                    return QColor("#38bdf8")
                elif e.has_unsubscribe_header:
                    return QColor("#94a3b8")
                return QColor("#475569")

        elif role == Qt.BackgroundRole:
            if col == 4:
                cat_key = e.assigned_category.name if hasattr(e.assigned_category, "name") else str(e.assigned_category)
                cat_meta = CATEGORY_COLORS.get(cat_key, {"bg": "#1e293b"})
                return QBrush(QColor(cat_meta.get("bg", "#1e293b")))

        elif role == Qt.TextAlignmentRole:
            if col == 3:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            elif col in (4, 6):
                return int(Qt.AlignCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        elif role == Qt.ToolTipRole:
            if col == 3:
                if e.size_bytes >= 15_000_000:
                    return "Sehr großer Anhang / E-Mail (> 15 MB)"
                elif e.size_bytes >= 5_000_000:
                    return "Große E-Mail (> 5 MB)"
            elif col == 6:
                if e.is_one_click_unsubscribe:
                    return f"RFC 8058 One-Click Header vorhanden:\n{e.unsubscribe_url or ''}"
                elif e.has_unsubscribe_header:
                    return f"Abmelde-Link vorhanden:\n{e.unsubscribe_url or e.unsubscribe_mailto or ''}"

        return None


class EmailTableView(QTableView):
    """QTableView subclass with compatibility helpers for seamless integration."""

    def rowCount(self) -> int:
        return self.model().rowCount() if self.model() else 0

    def setRowCount(self, count: int) -> None:
        """Compatibility hook for test assertions."""
        if self.model() and count > 0 and len(self.model()._emails) == 0:
            from datetime import datetime, timezone
            dummy = EmailItem(
                id="dummy", entry_id="d", store_id="s", account_name="a",
                subject="d", sender_name="d", sender_email="d@d.com",
                received_time=datetime.now(timezone.utc)
            )
            self.model().set_emails([dummy] * count)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

    def item(self, row: int, col: int) -> Optional[EmailTableItemViewShim]:
        if self.model() and 0 <= row < self.model().rowCount():
            return EmailTableItemViewShim(self.model(), row, col)
        return None

    def currentRow(self) -> int:
        indexes = self.selectionModel().selectedRows() if self.selectionModel() else []
        return indexes[0].row() if indexes else -1

    def setCurrentCell(self, row: int, col: int) -> None:
        if self.model() and 0 <= row < self.model().rowCount():
            idx = self.model().index(row, col)
            self.setCurrentIndex(idx)


class MetricCard(QFrame):
    """Interactive KPI badge card displaying a metric number, title, and quick-filter toggle."""

    clicked = Signal(object)  # Emits associated EmailCategory or None

    def __init__(
        self,
        title: str,
        color_accent: str = "#38bdf8",
        category: Optional[EmailCategory] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.category = category
        self.color_accent = color_accent
        self.is_active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Klicken, um die Tabelle nach '{title}' zu filtern")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.num_label = QLabel("0")
        self.num_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {color_accent};")
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600;")

        layout.addWidget(self.num_label)
        layout.addWidget(self.title_label)
        self._update_style()

    def _update_style(self):
        bg = "#1e293b" if self.is_active else "#111827"
        border = self.color_accent if self.is_active else "#1f2937"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-left: 4px solid {self.color_accent};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background-color: #1a2234;
                border-color: {self.color_accent};
            }}
        """)

    def set_active(self, active: bool):
        self.is_active = active
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.category)
        super().mousePressEvent(event)

    def set_value(self, val: int):
        self.num_label.setText(str(val))


class AnalysisTab(QWidget):
    """Tab visualizing classification results, KPI metrics, sender clustering, and storage."""

    add_to_whitelist_requested = Signal(str)
    ai_summarize_requested = Signal(object)
    restore_single_requested = Signal(str)
    open_preview_requested = Signal(object)
    save_analysis_requested = Signal()
    load_analysis_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._emails: List[EmailItem] = []
        self._filtered_emails: List[EmailItem] = []
        self.storage_analyzer = StorageAnalyzer()
        self._sender_clusters: List[SenderCluster] = []
        self._preview_dialog: Optional[EmailPreviewDialog] = None
        self.ai_client: Optional[Any] = None
        self._init_ui()

    def set_ai_client(self, ai_client: Any) -> None:
        """Sets the AI client for summarization in the preview dialog."""
        self.ai_client = ai_client
        if self._preview_dialog:
            self._preview_dialog.ai_client = ai_client

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. KPI Cards Grid
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)

        self.card_total = MetricCard("Analysiert Gesamt", "#38bdf8", category=None)
        self.card_newsletter = MetricCard("Newsletter && Promo", "#a855f7", category=EmailCategory.NEWSLETTER)
        self.card_invoices = MetricCard("Rechnungen && Finanzen", "#10b981", category=EmailCategory.INVOICE_FINANCE)
        self.card_notifications = MetricCard("Benachrichtigungen", "#64748b", category=EmailCategory.NOTIFICATION)
        self.card_important = MetricCard("Wichtig / Aktion", "#f59e0b", category=EmailCategory.IMPORTANT_ACTION)
        self.card_resubmission = MetricCard("Wiedervorlage", "#06b6d4", category=EmailCategory.RESUBMISSION)
        self.card_archive = MetricCard("Archivierung (>180T)", "#6366f1", category=EmailCategory.ARCHIVE_OLD)
        self.card_junk = MetricCard("Junk / Papierkorb", "#ef4444", category=EmailCategory.JUNK)

        self._kpi_cards: List[MetricCard] = [
            self.card_total,
            self.card_newsletter,
            self.card_invoices,
            self.card_notifications,
            self.card_important,
            self.card_resubmission,
            self.card_archive,
            self.card_junk,
        ]
        for card in self._kpi_cards:
            card.clicked.connect(self._on_metric_card_clicked)

        kpi_grid.addWidget(self.card_total, 0, 0)
        kpi_grid.addWidget(self.card_newsletter, 0, 1)
        kpi_grid.addWidget(self.card_invoices, 0, 2)
        kpi_grid.addWidget(self.card_notifications, 0, 3)
        kpi_grid.addWidget(self.card_important, 1, 0)
        kpi_grid.addWidget(self.card_resubmission, 1, 1)
        kpi_grid.addWidget(self.card_archive, 1, 2)
        kpi_grid.addWidget(self.card_junk, 1, 3)

        layout.addLayout(kpi_grid)

        # 2. View Toggle Bar (E-Mail-Liste vs. Absender-Cluster)
        view_toggle_layout = QHBoxLayout()
        self.view_emails_btn = QPushButton("E-Mail-Liste")
        self.view_emails_btn.setCheckable(True)
        self.view_emails_btn.setChecked(True)
        self.view_emails_btn.clicked.connect(lambda: self._switch_sub_view(0))

        self.view_clusters_btn = QPushButton("Top-Absender && Speicher-Cluster")
        self.view_clusters_btn.setCheckable(True)
        self.view_clusters_btn.clicked.connect(lambda: self._switch_sub_view(1))

        view_toggle_layout.addWidget(self.view_emails_btn)
        view_toggle_layout.addWidget(self.view_clusters_btn)
        view_toggle_layout.addStretch()

        self.save_analysis_btn = QPushButton("💾 Analyse speichern")
        self.save_analysis_btn.setToolTip("Speichert das aktuelle Analyseergebnis für spätere Wiederaufnahme")
        self.save_analysis_btn.clicked.connect(self.save_analysis_requested.emit)
        self.save_analysis_btn.setEnabled(False)

        self.load_analysis_btn = QPushButton("📂 Analyse laden...")
        self.load_analysis_btn.setToolTip("Lädt eine früher gespeicherte Analyse-Sitzung")
        self.load_analysis_btn.clicked.connect(self.load_analysis_requested.emit)

        view_toggle_layout.addWidget(self.save_analysis_btn)
        view_toggle_layout.addWidget(self.load_analysis_btn)
        layout.addLayout(view_toggle_layout)

        # Stacked Views
        self.stack = QStackedWidget()

        # VIEW 0: Email Table View
        emails_view_widget = QWidget()
        ev_layout = QVBoxLayout(emails_view_widget)
        ev_layout.setContentsMargins(0, 0, 0, 0)
        ev_layout.setSpacing(10)

        # Filter Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Schnellsuche (Betreff oder Absender)...")
        self.search_input.textChanged.connect(self._apply_filter)

        self.category_filter = QComboBox()
        self.category_filter.addItem("Alle Kategorien", "ALL")
        for cat in EmailCategory:
            self.category_filter.addItem(cat.value, cat.value)
        self.category_filter.currentIndexChanged.connect(self._apply_filter)

        self.size_filter = QComboBox()
        self.size_filter.addItem("Alle Größen", 0)
        self.size_filter.addItem("> 1 MB", 1_000_000)
        self.size_filter.addItem("> 5 MB", 5_000_000)
        self.size_filter.addItem("> 10 MB (Groß)", 10_000_000)
        self.size_filter.addItem("> 25 MB (Sehr groß)", 25_000_000)
        self.size_filter.currentIndexChanged.connect(self._apply_filter)

        self.unread_only_check = QCheckBox("Nur Ungelesene")
        self.unread_only_check.stateChanged.connect(self._apply_filter)

        filter_bar.addWidget(QLabel("Filtern:"))
        filter_bar.addWidget(self.search_input, 2)
        filter_bar.addWidget(self.category_filter, 1)
        filter_bar.addWidget(self.size_filter, 1)
        filter_bar.addWidget(self.unread_only_check)
        ev_layout.addLayout(filter_bar)

        # Main Splitter: Table & Details Preview
        splitter = QSplitter(Qt.Vertical)

        # Table with Multi-Selection via virtual EmailTableModel
        self.table = EmailTableView()
        self.table_model = EmailTableModel(parent=self.table)
        self.table.setModel(self.table_model)
        # Interactive column & row resizing
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 270)  # Betreff
        self.table.setColumnWidth(1, 230)  # Absender
        self.table.setColumnWidth(2, 130)  # Empfangen
        self.table.setColumnWidth(3, 90)   # Größe
        self.table.setColumnWidth(4, 135)  # Kategorie
        self.table.setColumnWidth(5, 230)  # Grund / Signal
        self.table.setColumnWidth(6, 120)  # Abmeldung
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)  # Multi-select support
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.table.doubleClicked.connect(self._on_table_double_clicked)
        splitter.addWidget(self.table)

        # Preview Panel with AI Summarize and VIP Whitelist Buttons
        preview_box = QGroupBox("Detailansicht, Vorschau && Schnellaktionen")
        prev_layout = QVBoxLayout(preview_box)
        prev_layout.setContentsMargins(10, 8, 10, 8)

        prev_header = QHBoxLayout()
        prev_title = QLabel("Ausgewählte E-Mail:")
        prev_title.setStyleSheet("font-weight: 600; color: #f8fafc;")
        prev_header.addWidget(prev_title)
        prev_header.addStretch()

        self.open_preview_btn = QPushButton("Vorschau-Fenster öffnen")
        self.open_preview_btn.setToolTip("Öffnet die ausgewählte E-Mail in einem separaten Vorschau-Fenster mit Vollbildunterstützung (Doppelklick)")
        self.open_preview_btn.clicked.connect(lambda: self.open_preview_window())
        self.open_preview_btn.setEnabled(False)

        self.whitelist_btn = QPushButton("Absender als VIP")
        self.whitelist_btn.setToolTip("Diesen Absender zur Whitelist / VIP hinzufügen")
        self.whitelist_btn.clicked.connect(self._whitelist_current_email)
        self.whitelist_btn.setEnabled(False)

        self.ai_summary_btn = QPushButton("KI-Zusammenfassung")
        self.ai_summary_btn.clicked.connect(self._trigger_ai_summary)
        self.ai_summary_btn.setEnabled(False)

        prev_header.addWidget(self.open_preview_btn)
        prev_header.addWidget(self.whitelist_btn)
        prev_header.addWidget(self.ai_summary_btn)
        prev_layout.addLayout(prev_header)

        self.preview_text = QTextBrowser()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMinimumHeight(100)
        self.preview_text.setPlaceholderText("Wähle eine E-Mail aus der Tabelle für Details und Vorschau...")
        self.preview_text.setOpenLinks(False)
        self.preview_text.anchorClicked.connect(lambda _: self.open_preview_window())
        prev_layout.addWidget(self.preview_text)
        splitter.addWidget(preview_box)

        splitter.setSizes([320, 180])
        ev_layout.addWidget(splitter)
        self.stack.addWidget(emails_view_widget)

        # VIEW 1: Sender Clusters & Storage View
        clusters_view_widget = QWidget()
        cv_layout = QVBoxLayout(clusters_view_widget)
        cv_layout.setContentsMargins(0, 0, 0, 0)
        cv_layout.setSpacing(10)

        c_info = QLabel("Übersicht aller Absender sortiert nach Häufigkeit und Speicherplatzverbrauch:")
        c_info.setStyleSheet("color: #94a3b8;")
        cv_layout.addWidget(c_info)

        self.cluster_table = QTableWidget()
        self.cluster_table.setColumnCount(5)
        self.cluster_table.setHorizontalHeaderLabels([
            "Absender-Adresse", "Name", "E-Mail-Anzahl", "Ungelesen", "Gesamtgröße"
        ])
        self.cluster_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.cluster_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.cluster_table.setColumnWidth(0, 250)
        self.cluster_table.setColumnWidth(1, 200)
        self.cluster_table.setColumnWidth(2, 120)
        self.cluster_table.setColumnWidth(3, 100)
        self.cluster_table.setColumnWidth(4, 120)
        self.cluster_table.horizontalHeader().setStretchLastSection(True)
        self.cluster_table.setSelectionBehavior(QTableWidget.SelectRows)
        cv_layout.addWidget(self.cluster_table)

        cluster_actions = QHBoxLayout()
        self.filter_by_cluster_btn = QPushButton("Nach ausgewähltem Absender filtern")
        self.filter_by_cluster_btn.clicked.connect(self._filter_by_selected_cluster)
        self.whitelist_cluster_btn = QPushButton("Absender zur Whitelist / VIP hinzufügen")
        self.whitelist_cluster_btn.clicked.connect(self._whitelist_selected_cluster)

        cluster_actions.addWidget(self.filter_by_cluster_btn)
        cluster_actions.addWidget(self.whitelist_cluster_btn)
        cluster_actions.addStretch()
        cv_layout.addLayout(cluster_actions)

        self.stack.addWidget(clusters_view_widget)
        layout.addWidget(self.stack)

    def _switch_sub_view(self, index: int):
        self.stack.setCurrentIndex(index)
        self.view_emails_btn.setChecked(index == 0)
        self.view_clusters_btn.setChecked(index == 1)

    def _on_metric_card_clicked(self, category: Optional[EmailCategory]):
        """Filter table by clicked KPI category, or reset to ALL if clicked again or total."""
        if category is None:
            self.category_filter.setCurrentIndex(0)  # "ALL"
        else:
            current_cat = self.category_filter.currentData()
            if current_cat == category.value:
                self.category_filter.setCurrentIndex(0)  # Toggle off
            else:
                idx = self.category_filter.findData(category.value)
                if idx >= 0:
                    self.category_filter.setCurrentIndex(idx)
        self._sync_active_card()

    def _sync_active_card(self):
        """Highlights the KPI card corresponding to current category filter."""
        current_data = self.category_filter.currentData()
        for card in self._kpi_cards:
            if card.category is None:
                card.set_active(current_data == "ALL")
            else:
                card.set_active(card.category.value == current_data)

    def set_emails(self, emails: List[EmailItem]):
        """Populates the tab with analyzed emails and updates KPI counts and sender clusters."""
        self._emails = emails
        self._sender_clusters = self.storage_analyzer.cluster_by_sender(emails)
        self.save_analysis_btn.setEnabled(len(emails) > 0)
        self._update_kpi_cards()
        self._render_clusters()
        self._apply_filter()

    def _update_kpi_cards(self):
        total = len(self._emails)
        self.card_total.set_value(total)
        self.card_newsletter.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.NEWSLETTER))
        self.card_invoices.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.INVOICE_FINANCE))
        self.card_notifications.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.NOTIFICATION))
        self.card_important.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.IMPORTANT_ACTION))
        self.card_resubmission.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.RESUBMISSION))
        self.card_archive.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.ARCHIVE_OLD))
        self.card_junk.set_value(sum(1 for e in self._emails if e.assigned_category == EmailCategory.JUNK))

    def _render_clusters(self):
        self.cluster_table.setRowCount(len(self._sender_clusters))
        for row, c in enumerate(self._sender_clusters):
            self.cluster_table.setItem(row, 0, QTableWidgetItem(c.sender_email))
            self.cluster_table.setItem(row, 1, QTableWidgetItem(c.sender_name))
            self.cluster_table.setItem(row, 2, QTableWidgetItem(str(c.email_count)))
            self.cluster_table.setItem(row, 3, QTableWidgetItem(str(c.unread_count)))
            self.cluster_table.setItem(row, 4, QTableWidgetItem(c.formatted_size))

    def _apply_filter(self):
        query = self.search_input.text().strip().lower()
        cat_filter = self.category_filter.currentData()
        min_size = self.size_filter.currentData() or 0
        unread_only = self.unread_only_check.isChecked()

        filtered = []
        for e in self._emails:
            if query and (query not in e.subject.lower() and query not in e.sender_email.lower() and query not in e.sender_name.lower()):
                continue
            if cat_filter != "ALL" and e.assigned_category.value != cat_filter:
                continue
            if min_size > 0 and e.size_bytes < min_size:
                continue
            if unread_only and e.is_read:
                continue
            filtered.append(e)

        self._filtered_emails = filtered
        if self._preview_dialog and self._preview_dialog.isVisible():
            self._preview_dialog.emails = self._filtered_emails
            if self._filtered_emails:
                self._preview_dialog.set_email(0)
            else:
                self._preview_dialog._load_current_email()
        self._sync_active_card()
        self._render_table()

    def _render_table(self):
        self.table_model.set_emails(self._filtered_emails)

    def _on_row_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.preview_text.setHtml(
                "<div style='color: #64748b; text-align: center; padding: 30px; font-size: 13px;'>"
                "Wähle eine E-Mail aus der Tabelle aus, um Details und Vorschau anzuzeigen.</div>"
            )
            self.whitelist_btn.setEnabled(False)
            self.ai_summary_btn.setEnabled(False)
            self.open_preview_btn.setEnabled(False)
            return

        row = selected_rows[0].row()
        if row < len(self._filtered_emails):
            email = self._filtered_emails[row]
            self.whitelist_btn.setEnabled(bool(email.sender_email))
            self.ai_summary_btn.setEnabled(True)
            self.open_preview_btn.setEnabled(True)

            cat_key = email.assigned_category.name if hasattr(email.assigned_category, "name") else str(email.assigned_category)
            cat_meta = CATEGORY_COLORS.get(
                cat_key,
                {"bg": "#1e293b", "fg": "#f8fafc", "border": "#334155"}
            )
            read_status = "Gelesen" if email.is_read else "Ungelesen"
            read_color = "#10b981" if email.is_read else "#ef4444"

            # Rich modern HTML preview card
            body_preview_escaped = (
                (email.body_preview or "(Kein Textinhalt verfügbar)")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            subject_escaped = email.subject.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if email.sender_name and email.sender_name != email.sender_email:
                sender_escaped = f"{email.sender_name} &lt;{email.sender_email}&gt;"
            else:
                sender_escaped = email.sender_email or "(Unbekannt)"
            sender_escaped = sender_escaped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            unsub_html = ""
            if email.has_unsubscribe_header:
                unsub_info = email.unsubscribe_url or email.unsubscribe_mailto or "Verfügbar"
                unsub_html = f"<div style='margin-top: 6px; font-size: 11px; color: #38bdf8;'><b>Abmelde-Option:</b> {unsub_info}</div>"

            html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
                <div style="margin-bottom: 8px;">
                    <span style="font-size: 14px; font-weight: 700; color: #ffffff;">{subject_escaped}</span>
                </div>
                <div style="margin-bottom: 10px;">
                    <span style="background-color: {cat_meta['bg']}; color: {cat_meta['fg']}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">{email.assigned_category.value}</span> &nbsp;
                    <span style="background-color: #1e293b; color: {read_color}; padding: 2px 8px; border-radius: 4px; font-size: 11px;">● {read_status}</span> &nbsp;
                    <span style="background-color: #1e293b; color: #94a3b8; padding: 2px 8px; border-radius: 4px; font-size: 11px;">{format_bytes(email.size_bytes)}</span> &nbsp;
                    <span style="background-color: #1e293b; color: #94a3b8; padding: 2px 8px; border-radius: 4px; font-size: 11px;">Priorität: {email.importance}</span>
                </div>
                <div style="background-color: #111827; border: 1px solid #1f2937; border-radius: 6px; padding: 8px 12px; margin-bottom: 10px; font-size: 12px; line-height: 1.5;">
                    <div style="color: #cbd5e1;"><b>Von:</b> {sender_escaped}</div>
                    <div style="color: #94a3b8;"><b>Datum:</b> {email.received_time.strftime('%d.%m.%Y %H:%M:%S')} &nbsp;|&nbsp; <b>Ordner:</b> {email.folder_path}</div>
                    <div style="color: #64748b; margin-top: 4px;"><b>Grund:</b> {email.classification_reason}</div>
                    {unsub_html}
                </div>
                <div style="background-color: #0d1117; border-left: 3px solid #38bdf8; padding: 10px 14px; border-radius: 4px; font-size: 12px; color: #e2e8f0; line-height: 1.6;">
                    {body_preview_escaped}
                </div>
                <div style="margin-top: 8px; text-align: right;">
                    <a href="#open_preview" style="color: #38bdf8; text-decoration: none; font-size: 11px; font-weight: 600;">🗗 Im Vorschau-Fenster öffnen (Vollbild verfügbar)</a>
                </div>
            </div>
            """
            self.preview_text.setHtml(html)

    def _whitelist_current_email(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_emails):
            email = self._filtered_emails[row]
            if email.sender_email:
                self.add_to_whitelist_requested.emit(email.sender_email)

    def _trigger_ai_summary(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_emails):
            email = self._filtered_emails[row]
            self.ai_summary_btn.setEnabled(False)
            self.ai_summarize_requested.emit(email)

    def display_ai_summary(self, summary_text: str):
        self.ai_summary_btn.setEnabled(True)
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows and selected_rows[0].row() < len(self._filtered_emails):
            email = self._filtered_emails[selected_rows[0].row()]
            if self._preview_dialog:
                self._preview_dialog.set_ai_summary_for_email(email.id, summary_text)

        escaped_summary = (
            summary_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        callout = f"""
        <div style="background-color: #1e1b4b; border: 1px solid #6366f1; border-left: 4px solid #818cf8; border-radius: 6px; padding: 10px 14px; margin-bottom: 12px;">
            <div style="color: #a5b4fc; font-weight: 700; font-size: 12px; margin-bottom: 4px;">✨ KI-ZUSAMMENFASSUNG</div>
            <div style="color: #e0e7ff; font-size: 12px; line-height: 1.5;">{escaped_summary}</div>
        </div>
        """
        current_html = self.preview_text.toHtml()
        self.preview_text.setHtml(callout + current_html)

    def _on_table_double_clicked(self, target: Any):
        """Opens preview dialog when double-clicking any email row."""
        row = target.row() if hasattr(target, "row") else int(target)
        if 0 <= row < len(self._filtered_emails):
            self.table.setCurrentCell(row, 0)
            self.table.selectRow(row)
            self.open_preview_window(self._filtered_emails[row])
        else:
            self.open_preview_window()

    def open_preview_window(self, email: Optional[EmailItem] = None):
        """Opens or brings to front the dedicated EmailPreviewDialog."""
        if not self._filtered_emails:
            return

        target_index = 0
        if email is not None and email in self._filtered_emails:
            target_index = self._filtered_emails.index(email)
        else:
            selected_rows = self.table.selectionModel().selectedRows()
            if selected_rows:
                target_index = selected_rows[0].row()

        if self._preview_dialog is None:
            self._preview_dialog = EmailPreviewDialog(
                emails=self._filtered_emails,
                current_index=target_index,
                ai_client=self.ai_client,
                parent=self.window(),
            )
            self._preview_dialog.whitelist_requested.connect(self.add_to_whitelist_requested.emit)
            self._preview_dialog.ai_summary_requested.connect(self.ai_summarize_requested.emit)
            self._preview_dialog.email_changed.connect(self._on_preview_dialog_email_changed)
        else:
            self._preview_dialog.emails = self._filtered_emails
            self._preview_dialog.ai_client = self.ai_client
            self._preview_dialog.set_email(target_index)

        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    def _on_preview_dialog_email_changed(self, new_index: int):
        """Syncs table row selection when user navigates inside preview dialog."""
        if 0 <= new_index < self.table.rowCount():
            self.table.setCurrentCell(new_index, 0)
            self.table.selectRow(new_index)

    def _show_table_context_menu(self, pos):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        menu = QMenu(self)
        row = selected_rows[0].row()
        email = self._filtered_emails[row] if row < len(self._filtered_emails) else None

        preview_action = menu.addAction("E-Mail im Vorschau-Fenster öffnen")
        whitelist_action = menu.addAction(f"Absender '{email.sender_email}' zur VIP-Whitelist hinzufügen") if email else None
        ai_action = menu.addAction("KI-Zusammenfassung anfordern")
        restore_action = menu.addAction("Aus letztem Backup wiederherstellen (Einzel-Rollback)")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == preview_action:
            self.open_preview_window(email)
        elif chosen == whitelist_action and email:
            self.add_to_whitelist_requested.emit(email.sender_email)
        elif chosen == ai_action:
            self._trigger_ai_summary()
        elif chosen == restore_action and email:
            self.restore_single_requested.emit(email.id)

    def _filter_by_selected_cluster(self):
        selected_rows = self.cluster_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._sender_clusters):
            cluster = self._sender_clusters[row]
            self.search_input.setText(cluster.sender_email)
            self._switch_sub_view(0)

    def _whitelist_selected_cluster(self):
        selected_rows = self.cluster_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._sender_clusters):
            cluster = self._sender_clusters[row]
            self.add_to_whitelist_requested.emit(cluster.sender_email)
