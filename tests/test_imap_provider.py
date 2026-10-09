"""Tests for ImapMailProvider and connection profile manager."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from py_inbox_helper.provider.imap_provider import ImapConfig, ImapMailProvider, ImapProfileManager


def test_imap_profile_manager(tmp_path: Path):
    manager = ImapProfileManager(config_path=tmp_path / "imap_profiles.json")
    assert len(manager.list_profiles()) == 0

    profile = ImapConfig(
        profile_id="prof-1",
        account_name="Mein Gmail Postfach",
        host="imap.gmail.com",
        port=993,
        use_ssl=True,
        username="daniel@gmail.com",
        password="app-password-123",
    )
    manager.save_profile(profile)

    loaded = manager.list_profiles()
    assert len(loaded) == 1
    assert loaded[0].account_name == "Mein Gmail Postfach"
    assert loaded[0].host == "imap.gmail.com"


@patch("imaplib.IMAP4_SSL")
def test_imap_provider_list_accounts_and_folders(mock_imap_cls, tmp_path: Path):
    manager = ImapProfileManager(config_path=tmp_path / "imap_profiles.json")
    manager.save_profile(ImapConfig(
        profile_id="prof-1",
        account_name="GMX Postfach",
        host="imap.gmx.net",
        username="user@gmx.de",
        password="secret",
    ))

    provider = ImapMailProvider(profile_manager=manager)
    accounts = provider.list_accounts()
    assert len(accounts) == 1
    assert accounts[0].id == "prof-1"

    # Mock IMAP instance
    mock_imap = MagicMock()
    mock_imap_cls.return_value = mock_imap
    mock_imap.login.return_value = ("OK", [b"Logged in"])
    mock_imap.list.return_value = ("OK", [
        b'(\\HasNoChildren) "/" "INBOX"',
        b'(\\HasNoChildren) "/" "Trash"',
    ])

    folders = provider.list_folders("prof-1")
    assert len(folders) == 2
    assert any(f.name == "INBOX" and f.is_inbox for f in folders)
