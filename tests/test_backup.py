"""Tests for BackupManager and rollback snapshot persistence."""
from datetime import datetime, timezone
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from py_inbox_helper.models import EmailItem, BackupSnapshot
from py_inbox_helper.backup import BackupManager


def test_create_and_save_snapshot(tmp_path: Path):
    manager = BackupManager(backup_dir=tmp_path)
    now = datetime.now(timezone.utc)
    email1 = EmailItem(
        id="item-1",
        entry_id="ENTRY-1",
        store_id="STORE-1",
        account_name="test@domain.com",
        subject="Wichtige Rechnung",
        sender_name="Firma A",
        sender_email="firma@a.de",
        received_time=now,
        is_read=True,
        importance="high",
        categories=["Buchhaltung"],
        folder_path="Posteingang",
    )
    email2 = EmailItem(
        id="item-2",
        entry_id="ENTRY-2",
        store_id="STORE-1",
        account_name="test@domain.com",
        subject="Newsletter",
        sender_name="Shop",
        sender_email="shop@b.de",
        received_time=now,
        is_read=False,
        importance="normal",
        categories=[],
        folder_path="Posteingang",
    )

    snapshot = manager.create_snapshot("test@domain.com", [email1, email2])
    assert len(snapshot.items) == 2
    assert snapshot.items[0].subject == "Wichtige Rechnung"
    assert snapshot.items[0].folder_path == "Posteingang"

    saved_file = manager.save_snapshot(snapshot)
    assert saved_file.exists()

    loaded = manager.load_snapshot(snapshot.snapshot_id)
    assert loaded is not None
    assert loaded.snapshot_id == snapshot.snapshot_id
    assert len(loaded.items) == 2
    assert loaded.items[1].is_read is False


def test_rollback_restoration(tmp_path: Path):
    manager = BackupManager(backup_dir=tmp_path)
    mock_provider = MagicMock()

    snapshot = manager.create_snapshot("test@domain.com", [
        EmailItem(
            id="item-1",
            entry_id="ENTRY-1",
            store_id="STORE-1",
            account_name="test@domain.com",
            subject="Test Mail",
            sender_name="Sender",
            sender_email="sender@mail.com",
            received_time=datetime.now(timezone.utc),
            is_read=True,
            importance="normal",
            categories=["CatA"],
            folder_path="Posteingang",
        )
    ])

    results = manager.restore_snapshot(snapshot, mock_provider)
    assert len(results) == 1
    assert results[0]["success"] is True

    mock_provider.restore_item.assert_called_once_with(
        entry_id="ENTRY-1",
        store_id="STORE-1",
        target_folder="Posteingang",
        is_read=True,
        categories=["CatA"],
    )


def test_granular_single_item_rollback(tmp_path: Path):
    manager = BackupManager(backup_dir=tmp_path)
    mock_provider = MagicMock()

    snapshot = manager.create_snapshot("test@domain.com", [
        EmailItem(
            id="item-1",
            entry_id="ENTRY-1",
            store_id="STORE-1",
            account_name="test@domain.com",
            subject="Mail 1",
            sender_name="Sender 1",
            sender_email="s1@mail.com",
            received_time=datetime.now(timezone.utc),
            folder_path="Posteingang",
        ),
        EmailItem(
            id="item-2",
            entry_id="ENTRY-2",
            store_id="STORE-1",
            account_name="test@domain.com",
            subject="Mail 2",
            sender_name="Sender 2",
            sender_email="s2@mail.com",
            received_time=datetime.now(timezone.utc),
            folder_path="Posteingang",
        ),
    ])

    # Only restore item-2
    results = manager.restore_items_by_id(snapshot, ["item-2"], mock_provider)
    assert len(results) == 1
    assert results[0]["entry_id"] == "ENTRY-2"
    assert results[0]["success"] is True

    mock_provider.restore_item.assert_called_once_with(
        entry_id="ENTRY-2",
        store_id="STORE-1",
        target_folder="Posteingang",
        is_read=False,
        categories=[],
    )

