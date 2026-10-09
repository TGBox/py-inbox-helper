"""Analysis overview tab displaying KPI metric cards, filters, and categorized email table."""
from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import Qt
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.models import EmailCategory, EmailItem


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
    """Tab visualizing classification results, KPI metrics, and raw email exploration."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._emails: List[EmailItem] = []
        self._filtered_emails: List[EmailItem] = []
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

        # 2. Filter Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Schnellsuche (Betreff oder Absender)...")
        self.search_input.textChanged.connect(self._apply_filter)

        self.category_filter = QComboBox()
        self.category_filter.addItem("Alle Kategorien", "ALL")
        for cat in EmailCategory:
            self.category_filter.addItem(cat.value, cat.value)
        self.category_filter.currentIndexChanged.connect(self._apply_filter)

        self.unread_only_check = QCheckBox("Nur Ungelesene")
        self.unread_only_check.stateChanged.connect(self._apply_filter)

        filter_bar.addWidget(QLabel("Filtern:"))
        filter_bar.addWidget(self.search_input, 2)
        filter_bar.addWidget(self.category_filter, 1)
        filter_bar.addWidget(self.unread_only_check)
        layout.addLayout(filter_bar)

        # 3. Main Splitter: Table & Details Preview
        splitter = QSplitter(Qt.Vertical)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Betreff", "Absender", "Empfangen", "Kategorie", "Grund / Signal", "Abmeldung"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.table)

        # Preview Panel
        preview_box = QGroupBox("Detailansicht & E-Mail-Vorschau")
        prev_layout = QVBoxLayout(preview_box)
        prev_layout.setContentsMargins(10, 10, 10, 10)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setPlaceholderText("Wähle eine E-Mail aus der Tabelle für Details...")
        prev_layout.addWidget(self.preview_text)
        splitter.addWidget(preview_box)

        splitter.setSizes([350, 150])
        layout.addWidget(splitter)

    def set_emails(self, emails: List[EmailItem]):
        """Populates the tab with analyzed emails and updates KPI counts."""
        self._emails = emails
        self._update_kpi_cards()
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

    def _apply_filter(self):
        query = self.search_input.text().strip().lower()
        cat_filter = self.category_filter.currentData()
        unread_only = self.unread_only_check.isChecked()

        filtered = []
        for e in self._emails:
            if query and (query not in e.subject.lower() and query not in e.sender_email.lower() and query not in e.sender_name.lower()):
                continue
            if cat_filter != "ALL" and e.assigned_category.value != cat_filter:
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

            # Category
            cat_item = QTableWidgetItem(e.assigned_category.value)
            self.table.setItem(row, 3, cat_item)

            # Reason
            self.table.setItem(row, 4, QTableWidgetItem(e.classification_reason))

            # Unsubscribe
            unsub_str = "One-Click verfügbar" if e.is_one_click_unsubscribe else ("Web-Link" if e.has_unsubscribe_header else "-")
            self.table.setItem(row, 5, QTableWidgetItem(unsub_str))

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
                f"Datum: {email.received_time.strftime('%d.%m.%Y %H:%M:%S')}",
                f"Ordner: {email.folder_path} | Gelesen: {'Ja' if email.is_read else 'Nein'} | Priorität: {email.importance}",
                f"Kategorie: {email.assigned_category.value} -> {email.classification_reason}",
            ]
            if email.has_unsubscribe_header:
                details.append(f"Abmelde-Optionen: URL={email.unsubscribe_url or '-'}, Mailto={email.unsubscribe_mailto or '-'}")
            details.append("-" * 60)
            details.append("Vorschau Inhalt:")
            details.append(email.body_preview or "(Kein Textinhalt verfügbar)")

            self.preview_text.setText("\n".join(details))
