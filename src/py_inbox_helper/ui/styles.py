"""Modern UI styles and tokens for PySide6 application."""

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0b0f19;
}

QWidget {
    font-family: "Segoe UI", -apple-system, Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: #e2e8f0;
}

/* Header bar */
#headerBar {
    background-color: #111827;
    border-bottom: 1px solid #1f2937;
    padding: 8px 16px;
}

#appTitle {
    font-size: 18px;
    font-weight: 700;
    color: #38bdf8;
}

#appSubtitle {
    font-size: 12px;
    color: #94a3b8;
}

/* Tab Bar */
QTabWidget::pane {
    border: 1px solid #1f2937;
    background-color: #0b0f19;
    top: -1px;
}

QTabBar::tab {
    background-color: #111827;
    color: #94a3b8;
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #1f2937;
    border-bottom: none;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #1e293b;
    color: #38bdf8;
    border-bottom: 2px solid #38bdf8;
}

QTabBar::tab:hover:!selected {
    background-color: #1f2937;
    color: #f1f5f9;
}

/* Group boxes and cards */
QGroupBox {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 20px;
    padding-left: 14px;
    padding-right: 14px;
    padding-bottom: 14px;
    font-weight: 600;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding-left: 10px;
    padding-right: 10px;
    background-color: #111827;
    border-radius: 4px;
}

/* Buttons */
QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #1e293b;
}

/* Primary Action Button */
QPushButton#primaryBtn {
    background-color: #0284c7;
    color: #ffffff;
    border: 1px solid #0369a1;
}

QPushButton#primaryBtn:hover {
    background-color: #0369a1;
}

QPushButton#primaryBtn:pressed {
    background-color: #075985;
}

/* Success / Apply Button */
QPushButton#successBtn {
    background-color: #16a34a;
    color: #ffffff;
    border: 1px solid #15803d;
}

QPushButton#successBtn:hover {
    background-color: #15803d;
}

/* Danger / Restore Button */
QPushButton#warningBtn {
    background-color: #d97706;
    color: #ffffff;
    border: 1px solid #b45309;
}

QPushButton#warningBtn:hover {
    background-color: #b45309;
}

/* Tables */
QTableWidget, QTableView {
    background-color: #111827;
    alternate-background-color: #0f172a;
    border: 1px solid #1f2937;
    border-radius: 6px;
    gridline-color: #1f2937;
    color: #e2e8f0;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 8px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 1px solid #334155;
    font-weight: 600;
}

/* Inputs & Combos */
QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f8fafc;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    selection-background-color: #0284c7;
    color: #f8fafc;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #334155;
    border-radius: 6px;
    background-color: #1e293b;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0284c7;
    border-radius: 5px;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #e2e8f0;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #475569;
    background-color: #1e293b;
}

QCheckBox::indicator:checked {
    background-color: #0284c7;
    border-color: #38bdf8;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0b0f19;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
