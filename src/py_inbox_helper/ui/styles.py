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

QScrollBar:horizontal {
    border: none;
    background: #0b0f19;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Splitters */
QSplitter::handle {
    background-color: #1e293b;
}

QSplitter::handle:horizontal {
    width: 6px;
    margin: 4px 1px;
    border-radius: 3px;
}

QSplitter::handle:vertical {
    height: 6px;
    margin: 1px 4px;
    border-radius: 3px;
}

QSplitter::handle:hover {
    background-color: #38bdf8;
}

/* Status Bar */
#statusBar {
    background-color: #0d131f;
    border-top: 1px solid #1e293b;
    padding: 6px 16px;
}

#statusText {
    color: #94a3b8;
    font-size: 12px;
}

#statusBadge {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}

/* Tooltips */
QToolTip {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #38bdf8;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}
"""

CATEGORY_COLORS = {
    "NEWSLETTER": {"bg": "#3b0764", "border": "#9333ea", "text": "#e9d5ff", "fg": "#e9d5ff", "badge": "NEWSLETTER"},
    "INVOICE_FINANCE": {"bg": "#022c22", "border": "#059669", "text": "#a7f3d0", "fg": "#a7f3d0", "badge": "RECHNUNG"},
    "NOTIFICATION": {"bg": "#1e293b", "border": "#475569", "text": "#cbd5e1", "fg": "#cbd5e1", "badge": "SYSTEM"},
    "IMPORTANT_ACTION": {"bg": "#451a03", "border": "#d97706", "text": "#fde68a", "fg": "#fde68a", "badge": "WICHTIG"},
    "RESUBMISSION": {"bg": "#083344", "border": "#0891b2", "text": "#a5f3fc", "fg": "#a5f3fc", "badge": "WIEDERVORLAGE"},
    "ARCHIVE_OLD": {"bg": "#1e1b4b", "border": "#4f46e5", "text": "#c7d2fe", "fg": "#c7d2fe", "badge": "ARCHIV"},
    "JUNK": {"bg": "#450a0a", "border": "#dc2626", "text": "#fecaca", "fg": "#fecaca", "badge": "JUNK"},
    "UNCLASSIFIED": {"bg": "#0f172a", "border": "#334155", "text": "#94a3b8", "fg": "#94a3b8", "badge": "OFFEN"},
}

