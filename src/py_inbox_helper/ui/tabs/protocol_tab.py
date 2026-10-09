"""Dry-Run simulation and change protocol tab with approvals and exports."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.models import ActionPlan, ExecutionResult
from py_inbox_helper.protocol import ProtocolGenerator


class ProtocolTab(QWidget):
    """Tab presenting the Dry-Run simulation, audit protocol, and execution trigger."""

    apply_changes_requested = Signal()
    run_dry_run_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.generator = ProtocolGenerator()
        self._current_plan: Optional[ActionPlan] = None
        self._dry_run_results: List[ExecutionResult] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Header & Status
        header_row = QHBoxLayout()
        self.status_badge = QLabel("DRY-RUN SIMULATION (Keine Änderungen ausgeführt)")
        self.status_badge.setStyleSheet("""
            background-color: #0369a1;
            color: #ffffff;
            font-weight: 700;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
        """)
        self.summary_label = QLabel("Noch keine Simulation durchgeführt.")
        self.summary_label.setStyleSheet("color: #94a3b8; font-size: 13px;")

        header_row.addWidget(self.status_badge)
        header_row.addWidget(self.summary_label, 1)

        self.simulate_btn = QPushButton("Dry-Run aktualisieren")
        self.simulate_btn.clicked.connect(self.run_dry_run_requested.emit)
        header_row.addWidget(self.simulate_btn)
        layout.addLayout(header_row)

        # 2. Table of actions
        table_box = QGroupBox("Änderungsprotokoll der geplanten Aktionen")
        t_layout = QVBoxLayout(table_box)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Aktiv", "Betreff", "Zielordner", "Gelesen", "Abmelden", "Simulations-Ergebnis"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        t_layout.addWidget(self.table)
        layout.addWidget(table_box)

        # 3. Export Buttons
        export_row = QHBoxLayout()
        self.export_html_btn = QPushButton("Änderungsprotokoll als HTML exportieren")
        self.export_html_btn.clicked.connect(self._export_html)
        self.export_json_btn = QPushButton("Als JSON exportieren")
        self.export_json_btn.clicked.connect(self._export_json)

        export_row.addWidget(self.export_html_btn)
        export_row.addWidget(self.export_json_btn)
        export_row.addStretch()
        layout.addLayout(export_row)

        # 4. Safety Notice Box
        safety_box = QGroupBox("Sicherheitsnetz & Bestätigung")
        s_layout = QVBoxLayout(safety_box)
        safety_text = QLabel(
            "Vor der Ausführung wird automatisch ein vollständiger Wiederherstellungspunkt gesichert.\n"
            "Es werden keine E-Mails permanent vernichtet (Löschen verschiebt in den Outlook-Papierkorb).\n"
            "Alle Änderungen können bei Bedarf im Tab 'Wiederherstellung' per 1-Klick rückgängig gemacht werden."
        )
        safety_text.setStyleSheet("color: #38bdf8; font-size: 12px;")
        s_layout.addWidget(safety_text)

        self.apply_btn = QPushButton("Änderungen jetzt verbindlich in Outlook anwenden")
        self.apply_btn.setObjectName("successBtn")
        self.apply_btn.setFixedHeight(44)
        self.apply_btn.clicked.connect(self._confirm_and_apply)
        s_layout.addWidget(self.apply_btn)

        layout.addWidget(safety_box)

    def set_simulation_results(self, plan: ActionPlan, results: List[ExecutionResult]):
        self._current_plan = plan
        self._dry_run_results = results

        summary = self.generator.build_summary(plan.account_name, results, is_dry_run=True)
        self.summary_label.setText(
            f"Geplant: {summary['total']} Aktionen | {summary['moved']} Verschiebungen | "
            f"{summary['marked_read']} als gelesen | {summary['unsubscribed']} Abmeldungen"
        )

        self.table.setRowCount(len(results))
        for row, r in enumerate(results):
            # 0: Checkbox
            check = QCheckBox()
            check.setChecked(r.action.is_enabled)
            check.stateChanged.connect(lambda state, a=r.action: setattr(a, "is_enabled", bool(state)))
            self.table.setCellWidget(row, 0, check)

            # 1: Subject
            self.table.setItem(row, 1, QTableWidgetItem(r.action.email_subject))

            # 2: Target folder
            folder_str = r.action.target_folder or "(Kein)"
            self.table.setItem(row, 2, QTableWidgetItem(folder_str))

            # 3: Mark read
            self.table.setItem(row, 3, QTableWidgetItem("Ja" if r.action.mark_as_read else "Nein"))

            # 4: Unsubscribe
            self.table.setItem(row, 4, QTableWidgetItem("Ja" if r.action.unsubscribe else "Nein"))

            # 5: Message
            self.table.setItem(row, 5, QTableWidgetItem(r.message))

    def _confirm_and_apply(self):
        if not self._current_plan or not self._dry_run_results:
            QMessageBox.information(self, "Hinweis", "Es liegt noch kein berechneter Aktionsplan vor.")
            return

        enabled_count = self._current_plan.enabled_count
        if enabled_count == 0:
            QMessageBox.warning(self, "Achtung", "Es sind keine Aktionen aktiviert.")
            return

        reply = QMessageBox.question(
            self,
            "Änderungen bestätigen",
            f"Möchtest du {enabled_count} Aktionen jetzt tatsächlich in deinem Postfach ausführen?\n\n"
            "Es wird vor der Ausführung automatisch ein Wiederherstellungspunkt gesichert.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.apply_changes_requested.emit()

    def _export_html(self):
        if not self._dry_run_results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Protokoll als HTML speichern", "Aenderungsprotokoll.html", "HTML (*.html)")
        if path:
            summary = self.generator.build_summary(self._current_plan.account_name if self._current_plan else "", self._dry_run_results, is_dry_run=True)
            self.generator.export_html(summary, self._dry_run_results, Path(path))
            QMessageBox.information(self, "Export erfolgreich", f"Das Protokoll wurde gespeichert unter:\n{path}")

    def _export_json(self):
        if not self._dry_run_results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Protokoll als JSON speichern", "Aenderungsprotokoll.json", "JSON (*.json)")
        if path:
            summary = self.generator.build_summary(self._current_plan.account_name if self._current_plan else "", self._dry_run_results, is_dry_run=True)
            self.generator.export_json(summary, self._dry_run_results, Path(path))
            QMessageBox.information(self, "Export erfolgreich", f"Die JSON-Datei wurde gespeichert unter:\n{path}")
