"""Tests for AnalysisStorageManager, AnalysisSession, and SavedAnalysesDialog."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from py_inbox_helper.analysis_storage import AnalysisStorageManager
from py_inbox_helper.models import AnalysisSession, EmailCategory, EmailItem
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.ui.main_window import MainWindow
from py_inbox_helper.ui.saved_analyses_dialog import SavedAnalysesDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _create_sample_email(email_id: str, subject: str = "Test Mail") -> EmailItem:
    return EmailItem(
        id=email_id,
        entry_id=f"entry_{email_id}",
        store_id="acc-1",
        account_name="test@example.com",
        subject=subject,
        sender_name="Sender",
        sender_email="sender@example.com",
        received_time=datetime.now(timezone.utc),
        body_preview="Preview text...",
        body_text="Full body text...",
        body_html="<p>Full HTML</p>",
        is_read=False,
        size_bytes=42000,
        folder_path="Posteingang",
        assigned_category=EmailCategory.INVOICE_FINANCE,
        classification_reason="Rechnung erkannt",
    )


def test_analysis_storage_manager_save_and_load(tmp_path: Path):
    manager = AnalysisStorageManager(storage_dir=tmp_path)
    emails = [_create_sample_email("m1"), _create_sample_email("m2")]

    session = manager.save_session(
        account_id="acc-1",
        account_name="Hauptkonto",
        emails=emails,
        notes="Erste Test-Analyse",
    )

    assert session.session_id.startswith("analysis_")
    assert len(session.emails) == 2

    # Check file exists on disk
    file_path = tmp_path / f"{session.session_id}.json"
    assert file_path.exists()

    # Load session
    loaded = manager.load_session(session.session_id)
    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert loaded.account_id == "acc-1"
    assert loaded.account_name == "Hauptkonto"
    assert loaded.notes == "Erste Test-Analyse"
    assert len(loaded.emails) == 2
    assert loaded.emails[0].subject == "Test Mail"
    assert loaded.emails[0].assigned_category == EmailCategory.INVOICE_FINANCE
    assert loaded.emails[0].body_text == "Full body text..."

    # Latest session
    latest = manager.load_latest_session()
    assert latest is not None
    assert latest.session_id == session.session_id


def test_analysis_storage_manager_list_and_delete(tmp_path: Path):
    manager = AnalysisStorageManager(storage_dir=tmp_path)
    emails = [_create_sample_email("m1")]

    s1 = manager.save_session("acc-1", "Konto 1", emails, notes="Session 1", custom_id="analysis_s1")
    s2 = manager.save_session("acc-2", "Konto 2", emails, notes="Session 2", custom_id="analysis_s2")

    sessions_meta = manager.list_sessions()
    assert len(sessions_meta) == 2
    session_ids = [s["session_id"] for s in sessions_meta]
    assert "analysis_s1" in session_ids
    assert "analysis_s2" in session_ids

    # Delete s1
    deleted = manager.delete_session("analysis_s1")
    assert deleted is True
    assert (tmp_path / "analysis_s1.json").exists() is False

    sessions_meta_after = manager.list_sessions()
    assert len(sessions_meta_after) == 1
    assert sessions_meta_after[0]["session_id"] == "analysis_s2"


def test_analysis_storage_export_and_import(tmp_path: Path):
    manager = AnalysisStorageManager(storage_dir=tmp_path / "storage")
    emails = [_create_sample_email("m1", subject="Exportierte E-Mail")]

    session = manager.save_session("acc-exp", "Export-Konto", emails, notes="Export-Notiz")

    export_path = tmp_path / "export" / "meine_analyse.json"
    manager.export_session(session.session_id, export_path)
    assert export_path.exists()

    # Import into another manager instance
    manager2 = AnalysisStorageManager(storage_dir=tmp_path / "storage2")
    imported = manager2.import_session(export_path)
    assert imported is not None
    assert len(imported.emails) == 1
    assert imported.emails[0].subject == "Exportierte E-Mail"
    assert len(manager2.list_sessions()) == 1


def test_saved_analyses_dialog(qapp, tmp_path: Path):
    manager = AnalysisStorageManager(storage_dir=tmp_path)
    emails = [_create_sample_email("m1"), _create_sample_email("m2")]
    session = manager.save_session("acc-1", "Hauptpostfach", emails, notes="Sitzung für UI Test")

    dialog = SavedAnalysesDialog(storage_manager=manager)
    dialog.show()

    # Table loaded
    assert dialog.table.rowCount() == 1
    assert "Hauptpostfach" in dialog.table.item(0, 1).text()
    assert "2 Mails" in dialog.table.item(0, 3).text()

    # Filter
    dialog.search_input.setText("NichtGefunden")
    assert dialog.table.rowCount() == 0
    dialog.search_input.setText("")
    assert dialog.table.rowCount() == 1

    # Fullscreen toggle
    assert dialog.isFullScreen() is False
    dialog.toggle_fullscreen()
    assert dialog.isFullScreen() is True
    dialog.toggle_fullscreen()
    assert dialog.isFullScreen() is False

    # Select and load
    dialog.table.selectRow(0)
    dialog._load_selected()
    assert dialog.selected_session is not None
    assert dialog.selected_session.session_id == session.session_id

    dialog.close()


def test_main_window_save_and_load_workflow(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path / "backups"
    window.analysis_storage = AnalysisStorageManager(storage_dir=tmp_path / "analyses")

    # 1. Scan emails
    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    analyzed = window.analyzer.analyze_batch(emails)
    window._on_scan_finished(analyzed)

    assert len(window.current_emails) > 0
    # Auto-saved session should exist
    saved_list = window.analysis_storage.list_sessions()
    assert len(saved_list) >= 1

    # 2. Clear current emails to simulate closing and re-opening app
    window.current_emails = []
    window.analysis_tab.set_emails([])
    assert len(window.current_emails) == 0
    assert window.analysis_tab.card_total.num_label.text() == "0"

    # 3. Restore from analysis storage
    latest_session = window.analysis_storage.load_latest_session()
    assert latest_session is not None
    window._load_analysis_session(latest_session)

    # 4. Verify emails and state are restored
    assert len(window.current_emails) == len(analyzed)
    assert window.tabs.currentIndex() == 1  # Switched to AnalysisTab
    assert int(window.analysis_tab.card_total.num_label.text()) == len(analyzed)
    assert window.analysis_tab.save_analysis_btn.isEnabled() is True
