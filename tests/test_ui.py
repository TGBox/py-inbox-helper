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


def test_ui_interactive_resizing_and_labels(qapp, tmp_path: Path):
    from PySide6.QtWidgets import QHeaderView
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    # Check button text in ProtocolTab
    assert "im Postfach anwenden" in window.protocol_tab.apply_btn.text()
    assert "in Outlook" not in window.protocol_tab.apply_btn.text()

    # Check interactive resize modes on tables (columns & rows)
    assert window.analysis_tab.table.horizontalHeader().sectionResizeMode(0) == QHeaderView.Interactive
    window.analysis_tab.table.setRowCount(1)
    assert window.analysis_tab.table.verticalHeader().sectionResizeMode(0) == QHeaderView.Interactive
    assert window.protocol_tab.table.horizontalHeader().sectionResizeMode(1) == QHeaderView.Interactive
    assert window.rules_tab.table.horizontalHeader().sectionResizeMode(1) == QHeaderView.Interactive
    assert window.backup_tab.table.horizontalHeader().sectionResizeMode(0) == QHeaderView.Interactive


def test_ui_dynamic_account_dropdown_and_folder_display(qapp, tmp_path: Path):
    from py_inbox_helper.provider.imap_provider import ImapConfig, ImapMailProvider, ImapProfileManager
    from py_inbox_helper.provider.base import FolderInfo

    profile_mgr = ImapProfileManager(config_path=tmp_path / "imap_profiles.json")
    profile = ImapConfig(
        profile_id="prof-custom-1",
        account_name="Mein Privates Postfach",
        host="imap.example.com",
        username="daniel@example.de",
    )
    profile_mgr.save_profile(profile)

    window = MainWindow(provider=MockMailProvider())
    window.imap_manager = profile_mgr
    window._refresh_provider_combo()

    # Verify combo contains the configured account
    combo_texts = [window.provider_combo.itemText(i) for i in range(window.provider_combo.count())]
    assert any("Mein Privates Postfach" in t for t in combo_texts)

    # Mock provider list_folders with RFC 3501 UTF-7 folder name
    mock_imap = ImapMailProvider(profile_manager=profile_mgr)
    window.scan_tab.provider = mock_imap
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mock_imap, "list_folders", lambda aid: [
            FolderInfo(id="INBOX", name="Posteingang", path="INBOX", is_inbox=True),
            FolderInfo(id="Entw&APw-rfe", name="Entwürfe", path="Entw&APw-rfe"),
            FolderInfo(id="Gel&APY-scht", name="Gelöscht", path="Gel&APY-scht"),
        ])
        window.scan_tab._load_folders_for_account("prof-custom-1")

        folder_items = [window.scan_tab.folder_list.item(i).text() for i in range(window.scan_tab.folder_list.count())]
        assert any("Entwürfe" in it for it in folder_items)
        assert any("Gelöscht" in it for it in folder_items)
        assert not any("Entw&APw-rfe" in it for it in folder_items)


def test_settings_dialog_initialization(qapp, tmp_path: Path):
    from py_inbox_helper.ui.settings_dialog import SettingsDialog
    from py_inbox_helper.ai import AiConfig
    from py_inbox_helper.analyzer import EmailAnalyzer
    from py_inbox_helper.provider.imap_provider import ImapProfileManager

    ai_cfg = AiConfig()
    analyzer = EmailAnalyzer()
    mgr = ImapProfileManager(config_path=tmp_path / "imap_profiles.json")

    # Open on tab 0
    dialog = SettingsDialog(ai_cfg, analyzer, mgr, initial_tab=0)
    assert dialog.tabs.count() == 3
    assert dialog.tabs.currentIndex() == 0

    # Open on tab 1 (IMAP accounts)
    dialog_imap = SettingsDialog(ai_cfg, analyzer, mgr, initial_tab=1)
    assert dialog_imap.tabs.currentIndex() == 1


def test_analysis_tab_kpi_card_filter_and_active_state(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    analyzed = window.analyzer.analyze_batch(emails)
    window._on_scan_finished(analyzed)

    analysis_tab = window.analysis_tab

    # Verify initial cards state (Gesamt card active)
    assert analysis_tab.card_total.is_active is True
    assert analysis_tab.card_newsletter.is_active is False

    # Simulate clicking Newsletter card
    analysis_tab.card_newsletter.clicked.emit(analysis_tab.card_newsletter.category)
    assert analysis_tab.category_filter.currentData() == "NEWSLETTER"
    assert analysis_tab.card_newsletter.is_active is True
    assert analysis_tab.card_total.is_active is False

    # All displayed emails should now be Newsletters
    for row in range(analysis_tab.table.rowCount()):
        assert "NEWSLETTER" in analysis_tab.table.item(row, 4).text()

    # Click Newsletter card again -> toggles off back to ALL
    analysis_tab.card_newsletter.clicked.emit(analysis_tab.card_newsletter.category)
    assert analysis_tab.category_filter.currentData() == "ALL"
    assert analysis_tab.card_total.is_active is True
    assert analysis_tab.table.rowCount() == len(analyzed)


def test_analysis_tab_table_formatting_and_preview(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    analyzed = window.analyzer.analyze_batch(emails)
    window._on_scan_finished(analyzed)

    analysis_tab = window.analysis_tab
    assert analysis_tab.table.rowCount() > 0

    # Test subject unread dot indicator and bold styling
    first_email = analysis_tab._filtered_emails[0]
    sub_text = analysis_tab.table.item(0, 0).text()
    if not first_email.is_read:
        assert "●" in sub_text
    else:
        assert "●" not in sub_text

    # Test category cell background color
    cat_item = analysis_tab.table.item(0, 4)
    assert cat_item.background().color().isValid()

    # Select row and test HTML preview rendering
    analysis_tab.table.selectRow(0)
    assert analysis_tab.whitelist_btn.isEnabled() is True
    assert analysis_tab.ai_summary_btn.isEnabled() is True
    html_content = analysis_tab.preview_text.toHtml()
    assert first_email.assigned_category.value in html_content

    # Clear selection and verify empty state
    analysis_tab.table.clearSelection()
    assert analysis_tab.whitelist_btn.isEnabled() is False
    assert analysis_tab.ai_summary_btn.isEnabled() is False
    assert "Wähle eine E-Mail" in analysis_tab.preview_text.toHtml()


def test_main_window_status_bar_and_shortcuts(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    # Initial status bar
    assert "Verbunden: Demo" in window.status_connection_lbl.text()
    assert "Keine Daten geladen" in window.status_data_lbl.text()

    # After loading emails
    emails = mock_provider.fetch_emails("acc-1", ["Posteingang"])
    analyzed = window.analyzer.analyze_batch(emails)
    window._on_scan_finished(analyzed)

    assert f"{len(emails)} E-Mails geladen" in window.status_data_lbl.text()

    # Test search focus helper (Ctrl+F)
    window.tabs.setCurrentIndex(0)
    window._focus_search()
    assert window.tabs.currentIndex() == 1


def test_scan_tab_horizontal_splitter_and_quick_pills(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    scan_tab = window.scan_tab
    assert scan_tab.splitter is not None
    assert scan_tab.splitter.count() == 2

    # Quick limit pill buttons
    scan_tab.pill_500.click()
    assert scan_tab.limit_spin.value() == 500

    scan_tab.pill_1000.click()
    assert scan_tab.limit_spin.value() == 1000

    scan_tab.pill_all.click()
    assert scan_tab.limit_spin.value() == 0  # 0 indicates 'Keine Begrenzung (Alle)'


def test_main_window_ai_status_indicators(qapp, tmp_path: Path):
    mock_provider = MockMailProvider()
    window = MainWindow(provider=mock_provider)
    window.backup_manager.backup_dir = tmp_path

    # Initial state with default disabled AI
    assert "KI: Deaktiviert" in window.status_ai_lbl.text()

    # Simulate AI check returning offline
    window.ai_config.provider = "ollama"
    window._on_ai_status_checked(False, "Verbindung abgelehnt")
    assert "KI: Offline (OLLAMA)" in window.status_ai_lbl.text()
    assert "Verbindung abgelehnt" in window.status_ai_lbl.toolTip()

    # Simulate AI check returning online / ready
    window._on_ai_status_checked(True, "Bereit (llama3.2)")
    assert "KI: Bereit (OLLAMA" in window.status_ai_lbl.text()
    assert "einsatzbereit" in window.status_ai_lbl.toolTip()
