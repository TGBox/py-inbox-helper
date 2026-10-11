"""Dedicated full email preview window with windowed and fullscreen modes, formatting, and AI."""
from __future__ import annotations

import html
from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from py_inbox_helper.models import EmailCategory, EmailItem
from py_inbox_helper.storage import format_bytes
from py_inbox_helper.ui.styles import CATEGORY_COLORS


class EmailPreviewDialog(QDialog):
    """Detailed preview window for analyzed emails.
    
    Supports both windowed and fullscreen modes (F11), interactive navigation
    across email lists, rich HTML/text views, headers inspection, and AI summarization.
    """

    whitelist_requested = Signal(str)
    ai_summary_requested = Signal(object)  # Emits EmailItem
    email_changed = Signal(int)  # Emits current index

    def __init__(
        self,
        emails: List[EmailItem],
        current_index: int = 0,
        ai_client: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowCloseButtonHint
        )
        self.emails: List[EmailItem] = emails
        self.current_index: int = max(0, min(current_index, len(emails) - 1)) if emails else 0
        self.ai_client = ai_client
        self._cached_ai_summaries: Dict[str, str] = {}

        self.resize(1050, 750)
        self._init_ui()
        self._setup_shortcuts()
        self._load_current_email()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        # 1. Top Action Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Navigation Controls
        self.prev_btn = QPushButton("◀ Vorherige (Alt+←)")
        self.prev_btn.setToolTip("Vorherige E-Mail in der Liste anzeigen")
        self.prev_btn.clicked.connect(self._show_previous)

        self.counter_label = QLabel("E-Mail 0 von 0")
        self.counter_label.setStyleSheet("color: #94a3b8; font-weight: 600; padding: 0 8px;")

        self.next_btn = QPushButton("Nächste (Alt+→) ▶")
        self.next_btn.setToolTip("Nächste E-Mail in der Liste anzeigen")
        self.next_btn.clicked.connect(self._show_next)

        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.counter_label)
        toolbar.addWidget(self.next_btn)
        toolbar.addSpacing(16)

        # Action Buttons
        self.whitelist_btn = QPushButton("Absender als VIP")
        self.whitelist_btn.setToolTip("Absender zur Whitelist / VIP-Liste hinzufügen")
        self.whitelist_btn.clicked.connect(self._on_whitelist_clicked)

        self.ai_summary_btn = QPushButton("✨ KI-Zusammenfassung")
        self.ai_summary_btn.setToolTip("Erstellt eine kompakte Zusammenfassung mit KI")
        self.ai_summary_btn.clicked.connect(self._on_ai_summary_clicked)

        self.copy_btn = QPushButton("Inhalt kopieren")
        self.copy_btn.setToolTip("Kopiert den E-Mail-Text in die Zwischenablage")
        self.copy_btn.clicked.connect(self._copy_email_content)

        toolbar.addWidget(self.whitelist_btn)
        toolbar.addWidget(self.ai_summary_btn)
        toolbar.addWidget(self.copy_btn)
        toolbar.addStretch()

        # Window Mode Controls
        self.fullscreen_btn = QPushButton("Vollbild (F11)")
        self.fullscreen_btn.setToolTip("Vollbildmodus aktivieren/deaktivieren (F11)")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        self.close_btn = QPushButton("Schließen (Esc)")
        self.close_btn.clicked.connect(self.close)

        toolbar.addWidget(self.fullscreen_btn)
        toolbar.addWidget(self.close_btn)
        main_layout.addLayout(toolbar)

        # 2. Metadata Header Card
        self.meta_card = QFrame()
        self.meta_card.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        meta_layout = QVBoxLayout(self.meta_card)
        meta_layout.setContentsMargins(14, 12, 14, 12)
        meta_layout.setSpacing(8)

        # Subject line
        self.subject_label = QLabel()
        self.subject_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.subject_label.setStyleSheet("font-size: 17px; font-weight: 700; color: #f8fafc;")
        meta_layout.addWidget(self.subject_label)

        # Badge row
        self.badge_row = QHBoxLayout()
        self.badge_row.setSpacing(8)

        self.category_badge = QLabel()
        self.category_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        """)

        self.read_badge = QLabel()
        self.read_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
        """)

        self.importance_badge = QLabel()
        self.importance_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
        """)

        self.size_badge = QLabel()
        self.size_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
        """)

        self.folder_badge = QLabel()
        self.folder_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
        """)

        self.badge_row.addWidget(self.category_badge)
        self.badge_row.addWidget(self.read_badge)
        self.badge_row.addWidget(self.importance_badge)
        self.badge_row.addWidget(self.size_badge)
        self.badge_row.addWidget(self.folder_badge)
        self.badge_row.addStretch()
        meta_layout.addLayout(self.badge_row)

        # Sender & Date details
        details_layout = QHBoxLayout()
        details_layout.setSpacing(20)

        self.sender_label = QLabel()
        self.sender_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.sender_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")

        self.date_label = QLabel()
        self.date_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.date_label.setStyleSheet("color: #94a3b8; font-size: 12px;")

        details_layout.addWidget(self.sender_label, 1)
        details_layout.addWidget(self.date_label)
        meta_layout.addLayout(details_layout)

        # Unsubscribe banner (optional)
        self.unsub_banner = QLabel()
        self.unsub_banner.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.unsub_banner.setStyleSheet("""
            background-color: #0c4a6e;
            color: #7dd3fc;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 11px;
        """)
        self.unsub_banner.setVisible(False)
        meta_layout.addWidget(self.unsub_banner)

        main_layout.addWidget(self.meta_card)

        # 3. Content Tabs
        self.tabs = QTabWidget()

        # Tab 1: Formatted / HTML view
        self.html_browser = QTextBrowser()
        self.html_browser.setOpenExternalLinks(True)
        self.html_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #0b0f19;
                color: #e2e8f0;
                border: 1px solid #1f2937;
                border-radius: 6px;
                padding: 16px;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        self.tabs.addTab(self.html_browser, "E-Mail Inhalt (Formatiert)")

        # Tab 2: Plain text view
        self.plain_text = QPlainTextEdit()
        self.plain_text.setReadOnly(True)
        self.plain_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b0f19;
                color: #e2e8f0;
                border: 1px solid #1f2937;
                border-radius: 6px;
                padding: 14px;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
            }
        """)
        self.tabs.addTab(self.plain_text, "Reiner Text")

        # Tab 3: Header & Raw Metadata View
        headers_widget = QWidget()
        hw_layout = QVBoxLayout(headers_widget)
        hw_layout.setContentsMargins(8, 8, 8, 8)
        hw_layout.setSpacing(8)

        self.header_search = QLineEdit()
        self.header_search.setPlaceholderText("Kopfzeile durchsuchen (z. B. List-Unsubscribe, From, Date)...")
        self.header_search.textChanged.connect(self._filter_headers_table)
        hw_layout.addWidget(self.header_search)

        self.headers_table = QTableWidget()
        self.headers_table.setColumnCount(2)
        self.headers_table.setHorizontalHeaderLabels(["Kopfzeile / Eigenschaft", "Wert"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.headers_table.setColumnWidth(0, 220)
        self.headers_table.verticalHeader().setVisible(False)
        self.headers_table.setSelectionBehavior(QTableWidget.SelectRows)
        hw_layout.addWidget(self.headers_table)
        self.tabs.addTab(headers_widget, "Kopfzeilen && Details")

        # Tab 4: AI & Classification Details
        self.ai_widget = QWidget()
        ai_layout = QVBoxLayout(self.ai_widget)
        ai_layout.setContentsMargins(14, 14, 14, 14)
        ai_layout.setSpacing(12)

        self.ai_status_label = QLabel()
        self.ai_status_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #a5b4fc;")
        ai_layout.addWidget(self.ai_status_label)

        self.ai_summary_box = QTextBrowser()
        self.ai_summary_box.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1b4b;
                color: #e0e7ff;
                border: 1px solid #4338ca;
                border-left: 4px solid #818cf8;
                border-radius: 6px;
                padding: 14px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        ai_layout.addWidget(self.ai_summary_box, 1)

        ai_btn_row = QHBoxLayout()
        self.gen_summary_btn = QPushButton("✨ KI-Zusammenfassung jetzt anfordern")
        self.gen_summary_btn.clicked.connect(self._on_ai_summary_clicked)
        ai_btn_row.addWidget(self.gen_summary_btn)
        ai_btn_row.addStretch()
        ai_layout.addLayout(ai_btn_row)

        self.tabs.addTab(self.ai_widget, "KI-Zusammenfassung && Analyse")

        main_layout.addWidget(self.tabs, 1)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for window control and list navigation."""
        # F11 Fullscreen toggle
        self.f11_sc = QShortcut(QKeySequence(Qt.Key_F11), self)
        self.f11_sc.activated.connect(self.toggle_fullscreen)

        # Esc closes fullscreen or closes dialog
        self.esc_sc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.esc_sc.activated.connect(self._handle_escape)

        # Alt+Left and Alt+Right for previous/next email navigation
        self.prev_sc = QShortcut(QKeySequence(Qt.AltModifier | Qt.Key_Left), self)
        self.prev_sc.activated.connect(self._show_previous)

        self.next_sc = QShortcut(QKeySequence(Qt.AltModifier | Qt.Key_Right), self)
        self.next_sc.activated.connect(self._show_next)

    def _handle_escape(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("Vollbild (F11)")
        else:
            self.close()

    def toggle_fullscreen(self):
        """Toggles between fullscreen and normal windowed mode."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText("Vollbild (F11)")
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("Fenstermodus (F11)")

    def _show_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_email()
            self.email_changed.emit(self.current_index)

    def _show_next(self):
        if self.current_index < len(self.emails) - 1:
            self.current_index += 1
            self._load_current_email()
            self.email_changed.emit(self.current_index)

    def set_email(self, index: int):
        """Sets the active email by index."""
        if 0 <= index < len(self.emails):
            self.current_index = index
            self._load_current_email()

    def _load_current_email(self):
        if not self.emails or self.current_index >= len(self.emails):
            self.setWindowTitle("E-Mail Vorschau - Keine E-Mails geladen")
            self.counter_label.setText("E-Mail 0 von 0")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            return

        total = len(self.emails)
        email = self.emails[self.current_index]

        self.setWindowTitle(f"E-Mail Vorschau: {email.subject}")
        self.counter_label.setText(f"E-Mail {self.current_index + 1} von {total}")
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < total - 1)

        # Subject & Sender
        self.subject_label.setText(email.subject or "(Kein Betreff)")
        if email.sender_name and email.sender_name != email.sender_email:
            sender_str = f"<b>Von:</b> {html.escape(email.sender_name)} &lt;{html.escape(email.sender_email)}&gt;"
        else:
            sender_str = f"<b>Von:</b> {html.escape(email.sender_email or '(Unbekannt)')}"
        self.sender_label.setText(sender_str)

        date_str = email.received_time.strftime("%d.%m.%Y um %H:%M:%S Uhr")
        self.date_label.setText(f"<b>Empfangen:</b> {date_str}")

        # Badges
        cat_key = email.assigned_category.name if hasattr(email.assigned_category, "name") else str(email.assigned_category)
        cat_meta = CATEGORY_COLORS.get(cat_key, {"bg": "#1e293b", "fg": "#f8fafc"})
        self.category_badge.setText(email.assigned_category.value)
        self.category_badge.setStyleSheet(f"""
            background-color: {cat_meta['bg']};
            color: {cat_meta['fg']};
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        """)

        read_text = "● Gelesen" if email.is_read else "● Ungelesen"
        read_col = "#10b981" if email.is_read else "#ef4444"
        self.read_badge.setText(read_text)
        self.read_badge.setStyleSheet(f"background-color: #1e293b; color: {read_col}; padding: 3px 10px; border-radius: 4px; font-size: 11px;")

        imp_col = "#ef4444" if email.importance.lower() == "high" else "#94a3b8"
        imp_map = {"high": "Hoch", "low": "Niedrig", "normal": "Normal"}
        imp_text = imp_map.get(email.importance.lower(), email.importance.capitalize())
        self.importance_badge.setText(f"Priorität: {imp_text}")
        self.importance_badge.setStyleSheet(f"background-color: #1e293b; color: {imp_col}; padding: 3px 10px; border-radius: 4px; font-size: 11px;")

        self.size_badge.setText(f"Größe: {format_bytes(email.size_bytes)}")
        self.folder_badge.setText(f"Ordner: {email.folder_path}")

        # Unsubscribe banner
        if email.is_one_click_unsubscribe:
            self.unsub_banner.setText(f"⚡ RFC 8058 One-Click Abmeldung verfügbar: {email.unsubscribe_url or ''}")
            self.unsub_banner.setVisible(True)
        elif email.has_unsubscribe_header:
            info = email.unsubscribe_url or email.unsubscribe_mailto or "Abmelde-Header vorhanden"
            self.unsub_banner.setText(f"🔗 Abmelde-Link vorhanden: {info}")
            self.unsub_banner.setVisible(True)
        else:
            self.unsub_banner.setVisible(False)

        # 1. HTML Content
        content_html = self._build_html_display(email)
        self.html_browser.setHtml(content_html)

        # 2. Plain text
        self.plain_text.setPlainText(email.display_body or "(Kein Textkörper vorhanden)")

        # 3. Headers table
        self._populate_headers_table(email)

        # 4. AI tab
        self._update_ai_tab(email)

    def _build_html_display(self, email: EmailItem) -> str:
        """Constructs an accessible, rich HTML view for the email content."""
        if email.body_html and len(email.body_html.strip()) > 10:
            # Render existing HTML body inside dark container
            return f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
                {email.body_html}
            </div>
            """
        else:
            # Format plain text with paragraphs and escaped content
            body = email.display_body or "(Kein Textinhalt verfügbar)"
            escaped_lines = html.escape(body).split("\n")
            formatted_paragraphs = "".join(f"<p style='margin: 0 0 10px 0;'>{line}</p>" if line.strip() else "<br>" for line in escaped_lines)
            return f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0; line-height: 1.6;">
                {formatted_paragraphs}
            </div>
            """

    def _populate_headers_table(self, email: EmailItem):
        """Populates the headers inspection table."""
        self._all_headers: List[tuple[str, str]] = [
            ("ID", email.id),
            ("Entry-ID", email.entry_id),
            ("Store-ID", email.store_id),
            ("Konto", email.account_name),
            ("Betreff", email.subject),
            ("Absender Name", email.sender_name),
            ("Absender E-Mail", email.sender_email),
            ("Empfangen", email.received_time.isoformat()),
            ("Ordner", email.folder_path),
            ("Größe", f"{email.size_bytes} Bytes ({format_bytes(email.size_bytes)})"),
            ("Kategorie", email.assigned_category.value),
            ("Klassifizierungs-Grund", email.classification_reason),
            ("Gelesen", "Ja" if email.is_read else "Nein"),
            ("Priorität", email.importance),
        ]
        for k, v in email.headers.items():
            self._all_headers.append((k, str(v)))

        self._filter_headers_table()

    def _filter_headers_table(self):
        query = self.header_search.text().strip().lower()
        filtered = [
            (k, v) for k, v in getattr(self, "_all_headers", [])
            if not query or query in k.lower() or query in v.lower()
        ]
        self.headers_table.setRowCount(len(filtered))
        for row, (k, v) in enumerate(filtered):
            k_item = QTableWidgetItem(k)
            k_item.setForeground(QColor("#38bdf8"))
            v_item = QTableWidgetItem(v)
            v_item.setForeground(QColor("#e2e8f0"))
            self.headers_table.setItem(row, 0, k_item)
            self.headers_table.setItem(row, 1, v_item)

    def _update_ai_tab(self, email: EmailItem):
        """Updates the AI analysis tab with classification insights or cached summaries."""
        status_text = f"Einstufung: {email.assigned_category.value} | Grund: {email.classification_reason}"
        self.ai_status_label.setText(status_text)

        if email.id in self._cached_ai_summaries:
            summary = self._cached_ai_summaries[email.id]
            self.ai_summary_box.setHtml(f"<b>KI-Zusammenfassung:</b><br><br>{html.escape(summary)}")
            self.gen_summary_btn.setText("✨ KI-Zusammenfassung erneut anfordern")
        else:
            self.ai_summary_box.setHtml(
                "<div style='color: #94a3b8; font-style: italic; padding: 20px 0;'>"
                "Noch keine KI-Zusammenfassung generiert.<br>"
                "Klicke auf den Button unten, um eine automatische Zusammenfassung zu erstellen.</div>"
            )
            self.gen_summary_btn.setText("✨ KI-Zusammenfassung jetzt anfordern")

    def _on_whitelist_clicked(self):
        if not self.emails or self.current_index >= len(self.emails):
            return
        email = self.emails[self.current_index]
        if email.sender_email:
            self.whitelist_requested.emit(email.sender_email)
            self.whitelist_btn.setText("✓ Absender ist VIP")
            self.whitelist_btn.setEnabled(False)

    def _on_ai_summary_clicked(self):
        if not self.emails or self.current_index >= len(self.emails):
            return
        email = self.emails[self.current_index]

        # Use passed ai_client directly if available, or emit signal
        if self.ai_client and hasattr(self.ai_client, "summarize_email"):
            self.gen_summary_btn.setEnabled(False)
            self.ai_summary_btn.setEnabled(False)
            self.ai_summary_box.setHtml("<i>KI analysiert E-Mail-Inhalt... bitte warten.</i>")
            QApplication.processEvents()
            try:
                summary = self.ai_client.summarize_email(email)
                self.set_ai_summary_for_email(email.id, summary)
            finally:
                self.gen_summary_btn.setEnabled(True)
                self.ai_summary_btn.setEnabled(True)
        else:
            self.ai_summary_requested.emit(email)

    def set_ai_summary_for_email(self, email_id: str, summary_text: str):
        """Caches and displays the AI summary for a given email."""
        self._cached_ai_summaries[email_id] = summary_text
        if self.emails and self.emails[self.current_index].id == email_id:
            self._update_ai_tab(self.emails[self.current_index])
            self.tabs.setCurrentIndex(3)  # Switch to AI tab to view result

    def _copy_email_content(self):
        """Copies the email text or subject to the system clipboard."""
        if not self.emails or self.current_index >= len(self.emails):
            return
        email = self.emails[self.current_index]
        text_to_copy = f"Betreff: {email.subject}\nVon: {email.sender_name} <{email.sender_email}>\nDatum: {email.received_time.isoformat()}\n\n{email.display_body}"
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text_to_copy)
            original_text = self.copy_btn.text()
            self.copy_btn.setText("✓ Kopiert!")
            QShortcut(QKeySequence(""), self, lambda: self.copy_btn.setText(original_text))
