"""Analysis overview tab displaying KPI metric cards, filters, sender clusters, and email table."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
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
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.models import EmailCategory, EmailItem
from py_inbox_helper.storage import SenderCluster, StorageAnalyzer, format_bytes


class MetricCard(QFrame):
    """Visual KPI badge card displaying a metric number and label."""

    def __init__(self, title: str, color_accent: str = "#38bdf8", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #111827;
                border: 1px solid #1f2937;
                border-left: 4px solid {color_accent};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.num_label = QLabel("0")
        self.num_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {color_accent};")
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;")

        layout.addWidget(self.num_label)
        layout.addWidget(self.title_label)

    def set_value(self, val: int):
        self.num_label.setText(str(val))


class AnalysisTab(QWidget):
    """Tab visualizing classification results, KPI metrics, sender clustering, and storage."""

    add_to_whitelist_requested = Signal(str)
    ai_summarize_requested = Signal(object)
    restore_single_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._emails: List[EmailItem] = []
        self._filtered_emails: List[EmailItem] = []
        self.storage_analyzer = StorageAnalyzer()
        self._sender_clusters: List[SenderCluster] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. KPI Cards Grid
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(12)

        self.card_total = MetricCard("Analysiert Gesamt", "#38bdf8")
        self.card_newsletter = MetricCard("Newsletter & Promo", "#a855f7")
        self.card_invoices = MetricCard("Rechnungen & Finanzen", "#10b981")
        self.card_notifications = MetricCard("Benachrichtigungen", "#64748b")
        self.card_important = MetricCard("Wichtig / Aktion", "#f59e0b")
        self.card_resubmission = MetricCard("Wiedervorlage", "#06b6d4")
        self.card_archive = MetricCard("Archivierung (>180T)", "#6366f1")
        self.card_junk = MetricCard("Junk / Papierkorb", "#ef4444")

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

        self.view_clusters_btn = QPushButton("Top-Absender & Speicher-Cluster")
        self.view_clusters_btn.setCheckable(True)
        self.view_clusters_btn.clicked.connect(lambda: self._switch_sub_view(1))

        view_toggle_layout.addWidget(self.view_emails_btn)
        view_toggle_layout.addWidget(self.view_clusters_btn)
        view_toggle_layout.addStretch()
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

        # Table with Multi-Selection
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Betreff", "Absender", "Empfangen", "Größe", "Kategorie", "Grund / Signal", "Abmeldung"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)  # Multi-select support
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        # Preview Panel with AI Summarize Button
        preview_box = QGroupBox("Detailansicht, Vorschau & KI-Assistent")
        prev_layout = QVBoxLayout(preview_box)
        prev_layout.setContentsMargins(10, 8, 10, 8)

        prev_header = QHBoxLayout()
        prev_header.addWidget(QLabel("Ausgewählte E-Mail:"))
        self.ai_summary_btn = QPushButton("KI-Zusammenfassung erstellen")
        self.ai_summary_btn.clicked.connect(self._trigger_ai_summary)
        prev_header.addStretch()
        prev_header.addWidget(self.ai_summary_btn)
        prev_layout.addLayout(prev_header)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setPlaceholderText("Wähle eine E-Mail aus der Tabelle für Details...")
        prev_layout.addWidget(self.preview_text)
        splitter.addWidget(preview_box)

        splitter.setSizes([320, 160])
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
        self.cluster_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cluster_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.cluster_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.cluster_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.cluster_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
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

    def set_emails(self, emails: List[EmailItem]):
        """Populates the tab with analyzed emails and updates KPI counts and sender clusters."""
        self._emails = emails
        self._sender_clusters = self.storage_analyzer.cluster_by_sender(emails)
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
        self._render_table()

    def _render_table(self):
        self.table.setRowCount(len(self._filtered_emails))
        for row, e in enumerate(self._filtered_emails):
            # Subject
            sub_item = QTableWidgetItem(e.subject)
            if not e.is_read:
                font = sub_item.font()
                font.setBold(True)
                sub_item.setFont(font)
            self.table.setItem(row, 0, sub_item)

            # Sender
            sender_str = f"{e.sender_name} <{e.sender_email}>" if e.sender_name else e.sender_email
            self.table.setItem(row, 1, QTableWidgetItem(sender_str))

            # Date
            date_str = e.received_time.strftime("%d.%m.%Y %H:%M")
            self.table.setItem(row, 2, QTableWidgetItem(date_str))

            # Size
            size_str = format_bytes(e.size_bytes)
            self.table.setItem(row, 3, QTableWidgetItem(size_str))

            # Category
            cat_item = QTableWidgetItem(e.assigned_category.value)
            self.table.setItem(row, 4, cat_item)

            # Reason
            self.table.setItem(row, 5, QTableWidgetItem(e.classification_reason))

            # Unsubscribe
            unsub_str = "One-Click verfügbar" if e.is_one_click_unsubscribe else ("Web-Link" if e.has_unsubscribe_header else "-")
            self.table.setItem(row, 6, QTableWidgetItem(unsub_str))

    def _on_row_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_emails):
            email = self._filtered_emails[row]
            details = [
                f"Betreff: {email.subject}",
                f"Absender: {email.sender_name} ({email.sender_email})",
                f"Datum: {email.received_time.strftime('%d.%m.%Y %H:%M:%S')} | Größe: {format_bytes(email.size_bytes)}",
                f"Ordner: {email.folder_path} | Gelesen: {'Ja' if email.is_read else 'Nein'} | Priorität: {email.importance}",
                f"Kategorie: {email.assigned_category.value} -> {email.classification_reason}",
            ]
            if email.has_unsubscribe_header:
                details.append(f"Abmelde-Optionen: URL={email.unsubscribe_url or '-'}, Mailto={email.unsubscribe_mailto or '-'}")
            details.append("-" * 60)
            details.append("Vorschau Inhalt:")
            details.append(email.body_preview or "(Kein Textinhalt verfügbar)")

            self.preview_text.setText("\n".join(details))

    def _trigger_ai_summary(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        if row < len(self._filtered_emails):
            email = self._filtered_emails[row]
            self.ai_summarize_requested.emit(email)

    def display_ai_summary(self, summary_text: str):
        current_text = self.preview_text.toPlainText()
        self.preview_text.setText(f"[KI-ZUSAMMENFASSUNG]:\n{summary_text}\n\n" + current_text)

    def _show_table_context_menu(self, pos):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        menu = QMenu(self)
        row = selected_rows[0].row()
        email = self._filtered_emails[row] if row < len(self._filtered_emails) else None

        whitelist_action = menu.addAction(f"Absender '{email.sender_email}' zur VIP-Whitelist hinzufügen") if email else None
        ai_action = menu.addAction("KI-Zusammenfassung anfordern")
        restore_action = menu.addAction("Aus letztem Backup wiederherstellen (Einzel-Rollback)")

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == whitelist_action and email:
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
