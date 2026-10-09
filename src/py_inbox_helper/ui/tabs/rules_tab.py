"""Rules and Action Configuration Tab with smart folder presets."""
from __future__ import annotations

from typing import Dict, List, Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.models import EmailCategory
from py_inbox_helper.planner import CategoryRulePreset, PlannerPresetConfig


class RulesTab(QWidget):
    """Tab allowing fine-grained customization of target folders and rule presets."""

    generate_plan_requested = Signal()

    def __init__(self, config: Optional[PlannerPresetConfig] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config or PlannerPresetConfig()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header description
        info_label = QLabel(
            "Passe hier die automatischen Aktionen für jede erkannte Kategorie an.\n"
            "Zielordner werden bei Bedarf automatisch in Outlook angelegt. "
            "Aktionen werden erst nach dem Dry-Run und deiner ausdrücklichen Bestätigung ausgeführt."
        )
        info_label.setStyleSheet("color: #94a3b8; font-size: 13px;")
        layout.addWidget(info_label)

        # Rules Table
        rules_box = QGroupBox("Kategorie-Regeln & Zielordner-Presets")
        r_layout = QVBoxLayout(rules_box)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Kategorie", "Zielordner", "Als gelesen", "Jahres-Unterordner", "Newsletter abmelden"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self._populate_table()
        r_layout.addWidget(self.table)
        layout.addWidget(rules_box)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        self.reset_btn = QPushButton("Auf Standard-Presets zurücksetzen")
        self.reset_btn.clicked.connect(self._reset_defaults)

        self.generate_btn = QPushButton("Aktionsplan mit diesen Regeln erstellen")
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.setFixedHeight(40)
        self.generate_btn.clicked.connect(self._save_and_generate)

        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.generate_btn)
        layout.addLayout(btn_layout)

    def _populate_table(self):
        categories = [
            EmailCategory.NEWSLETTER,
            EmailCategory.INVOICE_FINANCE,
            EmailCategory.NOTIFICATION,
            EmailCategory.IMPORTANT_ACTION,
            EmailCategory.RESUBMISSION,
            EmailCategory.ARCHIVE_OLD,
            EmailCategory.JUNK,
        ]

        self.table.setRowCount(len(categories))
        for row, cat in enumerate(categories):
            rule = self.config.category_rules.get(cat, CategoryRulePreset(target_folder=None))

            # 0: Category name
            cat_item = QTableWidgetItem(cat.value)
            cat_item.setData(1000, cat)
            self.table.setItem(row, 0, cat_item)

            # 1: Target Folder Input
            folder_edit = QLineEdit(rule.target_folder or "")
            self.table.setCellWidget(row, 1, folder_edit)

            # 2: Mark read Checkbox
            read_check = QCheckBox()
            read_check.setChecked(rule.mark_as_read)
            read_check.setStyleSheet("margin-left: 20px;")
            self.table.setCellWidget(row, 2, read_check)

            # 3: Year Subfolder Checkbox
            year_check = QCheckBox()
            year_check.setChecked(rule.use_year_subfolder)
            year_check.setStyleSheet("margin-left: 20px;")
            self.table.setCellWidget(row, 3, year_check)

            # 4: Unsubscribe Checkbox
            unsub_check = QCheckBox()
            unsub_check.setChecked(rule.offer_unsubscribe)
            unsub_check.setStyleSheet("margin-left: 20px;")
            self.table.setCellWidget(row, 4, unsub_check)

    def _save_and_generate(self):
        """Reads inputs from table and writes back to config."""
        for row in range(self.table.rowCount()):
            cat_item = self.table.item(row, 0)
            cat = cat_item.data(1000)

            folder_widget: QLineEdit = self.table.cellWidget(row, 1)
            read_widget: QCheckBox = self.table.cellWidget(row, 2)
            year_widget: QCheckBox = self.table.cellWidget(row, 3)
            unsub_widget: QCheckBox = self.table.cellWidget(row, 4)

            folder_val = folder_widget.text().strip() or None
            self.config.category_rules[cat] = CategoryRulePreset(
                target_folder=folder_val,
                mark_as_read=read_widget.isChecked(),
                use_year_subfolder=year_widget.isChecked(),
                offer_unsubscribe=unsub_widget.isChecked(),
            )

        self.generate_plan_requested.emit()

    def _reset_defaults(self):
        self.config = PlannerPresetConfig()
        self._populate_table()
