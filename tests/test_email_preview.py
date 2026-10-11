"""Tests for EmailPreviewDialog and integration with AnalysisTab."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime, timezone
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from py_inbox_helper.models import EmailCategory, EmailItem
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.ui.email_preview_dialog import EmailPreviewDialog
from py_inbox_helper.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_preview_dialog_initialization(qapp):
    now = datetime.now(timezone.utc)
    email1 = EmailItem(
        id="item-1",
        entry_id="EID-1",
        store_id="acc-1",
        account_name="test@example.com",
        subject="Rechnung September 2026",
        sender_name="Buchhaltung GmbH",
        sender_email="rechnung@firma.de",
        received_time=now,
        body_preview="Anbei Ihre Rechnung über 100 EUR...",
        body_text="Sehr geehrte Damen und Herren,\n\nanbei erhalten Sie die Rechnung.\n\nMit freundlichen Grüßen",
        body_html="<p>Sehr geehrte Damen und Herren,</p><p>anbei die Rechnung.</p>",
        is_read=False,
        importance="high",
        size_bytes=102400,
        folder_path="Posteingang",
        headers={"From": "rechnung@firma.de", "To": "test@example.com"},
        assigned_category=EmailCategory.INVOICE_FINANCE,
        classification_reason="Enthält Signalwörter für Rechnung",
    )
    email2 = EmailItem(
        id="item-2",
        entry_id="EID-2",
        store_id="acc-1",
        account_name="test@example.com",
        subject="Tech Newsletter #42",
        sender_name="Tech News",
        sender_email="news@tech.io",
        received_time=now,
        body_preview="Die Top-Trends der Woche...",
        body_text="Hallo! Hier sind die News...",
        is_read=True,
        headers={"List-Unsubscribe": "<https://tech.io/unsub>"},
        assigned_category=EmailCategory.NEWSLETTER,
    )

    dialog = EmailPreviewDialog(emails=[email1, email2], current_index=0)
    dialog.show()

    # Title & Counter
    assert "Rechnung September 2026" in dialog.windowTitle()
    assert dialog.counter_label.text() == "E-Mail 1 von 2"
    assert dialog.prev_btn.isEnabled() is False
    assert dialog.next_btn.isEnabled() is True

    # Badges
    assert dialog.category_badge.text() == EmailCategory.INVOICE_FINANCE.value
    assert "Ungelesen" in dialog.read_badge.text()
    assert "Hoch" in dialog.importance_badge.text()
    assert "100.0 KB" in dialog.size_badge.text()

    # Content tabs
    assert dialog.tabs.count() == 4
    assert "anbei die Rechnung" in dialog.html_browser.toHtml()
    assert "Sehr geehrte Damen und Herren" in dialog.plain_text.toPlainText()

    # Headers table
    assert dialog.headers_table.rowCount() >= 2
    dialog.close()


def test_preview_dialog_navigation(qapp):
    now = datetime.now(timezone.utc)
    emails = [
        EmailItem(
            id=f"item-{i}",
            entry_id=f"EID-{i}",
            store_id="acc-1",
            account_name="test@example.com",
            subject=f"Mail Nummer {i}",
            sender_name=f"Sender {i}",
            sender_email=f"sender{i}@example.com",
            received_time=now,
            body_preview=f"Inhalt {i}",
        )
        for i in range(3)
    ]

    dialog = EmailPreviewDialog(emails=emails, current_index=0)
    dialog.show()

    assert dialog.current_index == 0
    assert dialog.prev_btn.isEnabled() is False
    assert dialog.next_btn.isEnabled() is True

    # Navigate Next
    dialog._show_next()
    assert dialog.current_index == 1
    assert dialog.counter_label.text() == "E-Mail 2 von 3"
    assert dialog.prev_btn.isEnabled() is True
    assert dialog.next_btn.isEnabled() is True
    assert "Mail Nummer 1" in dialog.subject_label.text()

    # Navigate Next to Last
    dialog._show_next()
    assert dialog.current_index == 2
    assert dialog.counter_label.text() == "E-Mail 3 von 3"
    assert dialog.prev_btn.isEnabled() is True
    assert dialog.next_btn.isEnabled() is False

    # Navigate Back
    dialog._show_previous()
    assert dialog.current_index == 1
    assert dialog.counter_label.text() == "E-Mail 2 von 3"
    dialog.close()


def test_preview_dialog_fullscreen_toggle(qapp):
    now = datetime.now(timezone.utc)
    email = EmailItem(
        id="item-1",
        entry_id="EID-1",
        store_id="acc-1",
        account_name="test@example.com",
        subject="Fullscreen Test",
        sender_name="Sender",
        sender_email="sender@example.com",
        received_time=now,
    )
    dialog = EmailPreviewDialog(emails=[email], current_index=0)
    dialog.show()

    assert dialog.isFullScreen() is False
    assert "Vollbild" in dialog.fullscreen_btn.text()

    # Enter Fullscreen
    dialog.toggle_fullscreen()
    assert dialog.isFullScreen() is True
    assert "Fenstermodus" in dialog.fullscreen_btn.text()

    # Exit Fullscreen
    dialog.toggle_fullscreen()
    assert dialog.isFullScreen() is False
    assert "Vollbild" in dialog.fullscreen_btn.text()

    # Esc key in fullscreen exits fullscreen
    dialog.toggle_fullscreen()
    assert dialog.isFullScreen() is True
    dialog._handle_escape()
    assert dialog.isFullScreen() is False

    dialog.close()


def test_preview_dialog_headers_filter_and_copy(qapp):
    now = datetime.now(timezone.utc)
    email = EmailItem(
        id="item-1",
        entry_id="EID-1",
        store_id="acc-1",
        account_name="test@example.com",
        subject="Header Test",
        sender_name="Tester",
        sender_email="tester@example.com",
        received_time=now,
        body_text="Test Body For Copying",
        headers={"X-Spam-Score": "0.0", "List-Unsubscribe": "<https://example.com/unsub>"},
    )
    dialog = EmailPreviewDialog(emails=[email], current_index=0)

    # Filter headers
    dialog.header_search.setText("Unsubscribe")
    assert dialog.headers_table.rowCount() == 1
    assert dialog.headers_table.item(0, 0).text() == "List-Unsubscribe"

    dialog.header_search.setText("")
    assert dialog.headers_table.rowCount() > 5

    # Test copy content
    dialog._copy_email_content()
    clipboard_text = QApplication.clipboard().text()
    assert "Header Test" in clipboard_text
    assert "Test Body For Copying" in clipboard_text
    dialog.close()


def test_analysis_tab_opens_preview_window(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    window._on_scan_finished(emails)

    analysis_tab = window.analysis_tab
    assert analysis_tab.table.rowCount() == len(emails)

    # Select row 0
    analysis_tab.table.selectRow(0)
    assert analysis_tab.open_preview_btn.isEnabled() is True

    # Open preview window via button
    analysis_tab.open_preview_btn.click()
    assert analysis_tab._preview_dialog is not None
    assert analysis_tab._preview_dialog.isVisible() is True
    assert analysis_tab._preview_dialog.current_index == 0

    # Double click on row 1 opens preview dialog with row 1 email
    analysis_tab._on_table_double_clicked(analysis_tab.table.item(1, 0))
    assert analysis_tab._preview_dialog.current_index == 1

    # Dialog navigation syncs table selection
    analysis_tab._preview_dialog._show_next()
    assert analysis_tab.table.currentRow() == 2

    # Whitelist from preview dialog
    initial_whitelist_len = len(window.analyzer.config.whitelist_senders)
    target_sender = analysis_tab._preview_dialog.emails[2].sender_email
    analysis_tab._preview_dialog._on_whitelist_clicked()
    assert len(window.analyzer.config.whitelist_senders) == initial_whitelist_len + 1
    assert target_sender in window.analyzer.config.whitelist_senders

    analysis_tab._preview_dialog.close()
