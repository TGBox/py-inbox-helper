"""Tests for mail provider abstraction and mock implementation."""
from datetime import datetime, timezone
import pytest

from py_inbox_helper.provider.base import BaseMailProvider
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.models import PlannedAction, ActionType


def test_mock_provider_list_accounts_and_folders():
    provider = MockMailProvider()
    accounts = provider.list_accounts()
    assert len(accounts) >= 2
    assert any("Hauptkonto" in a.name or "office365" in a.name.lower() for a in accounts)

    primary_id = accounts[0].id
    folders = provider.list_folders(primary_id)
    assert len(folders) >= 3
    folder_names = [f.name for f in folders]
    assert "Posteingang" in folder_names


def test_mock_provider_fetch_emails():
    provider = MockMailProvider()
    accounts = provider.list_accounts()
    emails = provider.fetch_emails(
        account_id=accounts[0].id,
        folder_paths=["Posteingang"],
    )
    assert len(emails) > 0
    assert all(e.folder_path == "Posteingang" for e in emails)


def test_mock_provider_execute_and_restore():
    provider = MockMailProvider()
    accounts = provider.list_accounts()
    emails = provider.fetch_emails(accounts[0].id, ["Posteingang"])
    sample = emails[0]

    action = PlannedAction(
        email_id=sample.id,
        email_subject=sample.subject,
        action_type=ActionType.MOVE_AND_MARK_READ,
        target_folder="04_Newsletter",
        mark_as_read=True,
    )
    result = provider.execute_action(action, accounts[0].id)
    assert result.success is True

    # Check that item moved in mock state
    moved_item = provider.get_item(sample.entry_id, sample.store_id)
    assert moved_item.folder_path == "04_Newsletter"
    assert moved_item.is_read is True

    # Restore item back
    provider.restore_item(
        entry_id=sample.entry_id,
        store_id=sample.store_id,
        target_folder="Posteingang",
        is_read=False,
        categories=[],
    )
    restored_item = provider.get_item(sample.entry_id, sample.store_id)
    assert restored_item.folder_path == "Posteingang"
    assert restored_item.is_read is False


def test_mock_provider_fetch_with_naive_date_filters():
    provider = MockMailProvider()
    accounts = provider.list_accounts()
    # Pass offset-naive datetimes as filter
    naive_from = datetime(2020, 1, 1)  # no tzinfo!
    naive_to = datetime(2030, 1, 1)    # no tzinfo!

    emails = provider.fetch_emails(
        account_id=accounts[0].id,
        folder_paths=["Posteingang"],
        date_from=naive_from,
        date_to=naive_to,
    )
    assert len(emails) > 0

