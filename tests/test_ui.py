"""Integration tests for PySide6 MainWindow and complete workflow."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime, timezone
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication

from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_initialization(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    assert window.windowTitle() == "py-inbox-helper - E-Mail Postfach Assistent"
    assert window.tabs.count() == 5
    assert window.scan_tab.account_combo.count() >= 2


def test_main_window_fullscreen_toggle(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path
    window.show()

    # Initially not fullscreen
    assert window.isFullScreen() is False

    # Toggle to Fullscreen
    window.toggle_fullscreen()
    assert window.isFullScreen() is True
    assert "Fenstermodus" in window.fullscreen_btn.text()

    # Toggle back to Windowed mode
    window.toggle_fullscreen()
    assert window.isFullScreen() is False
    assert "Vollbild" in window.fullscreen_btn.text()


def test_main_window_full_workflow_end_to_end(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    # 1. Trigger scan synchronously
    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    analyzed = window.analyzer.analyze_batch(emails)
    window._on_scan_finished(analyzed)

    assert len(window.current_emails) > 0
    assert window.tabs.currentIndex() == 1  # Switched to AnalysisTab
    assert int(window.analysis_tab.card_total.num_label.text()) == len(analyzed)

    # 2. Generate Plan & Dry Run
    window._generate_plan_and_dry_run()
    assert window.tabs.currentIndex() == 3  # Switched to ProtocolTab
    assert window.current_plan is not None
    assert len(window.protocol_tab._dry_run_results) == len(analyzed)

    # 3. Export HTML and JSON
    html_out = tmp_path / "test_report.html"
    json_out = tmp_path / "test_report.json"
    summary = window.protocol_tab.generator.build_summary("acc-1", window.protocol_tab._dry_run_results, is_dry_run=True)
    window.protocol_tab.generator.export_html(summary, window.protocol_tab._dry_run_results, html_out)
    window.protocol_tab.generator.export_json(summary, window.protocol_tab._dry_run_results, json_out)
    assert html_out.exists()
    assert json_out.exists()

    # 4. Create snapshot and execute actions
    snapshot = window.backup_manager.create_snapshot("acc-1", window.current_emails)
    saved_file = window.backup_manager.save_snapshot(snapshot)
    assert saved_file.exists()

    # 5. Restore snapshot (Rollback)
    restore_results = window.backup_manager.restore_snapshot(snapshot, mock_provider)
    assert len(restore_results) == len(window.current_emails)
    assert all(r["success"] is True for r in restore_results)


def test_main_window_sender_clusters_and_whitelist(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    window._on_scan_finished(emails)

    # Check clusters populated
    assert len(window.analysis_tab._sender_clusters) > 0
    assert window.analysis_tab.cluster_table.rowCount() == len(window.analysis_tab._sender_clusters)

    # Whitelist a sender
    initial_wl_count = len(window.analyzer.config.whitelist_senders)
    target_sender = window.analysis_tab._sender_clusters[0].sender_email
    window._add_to_whitelist(target_sender)

    assert len(window.analyzer.config.whitelist_senders) == initial_wl_count + 1
    assert target_sender in window.analyzer.config.whitelist_senders


def test_main_window_granular_restore_flow(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    snapshot = window.backup_manager.create_snapshot("acc-1", emails)
    window.backup_manager.save_snapshot(snapshot)

    window.backup_tab.reload_snapshots()
    assert window.backup_tab.table.rowCount() >= 1

    # Check items populated in items_table
    assert window.backup_tab.items_table.rowCount() == len(emails)

    # Granular restore
    target_id = emails[0].id
    results = window.backup_manager.restore_items_by_id(snapshot, [target_id], mock_provider)
    assert len(results) == 1
    assert results[0]["success"] is True

