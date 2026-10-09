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


def test_decode_imap_utf7():
    from py_inbox_helper.provider.imap_provider import decode_imap_utf7
    assert decode_imap_utf7("Entw&APw-rfe") == "Entwürfe"
    assert decode_imap_utf7("Gel&APY-scht") == "Gelöscht"
    assert decode_imap_utf7("Posteingang") == "Posteingang"
    assert decode_imap_utf7("Filter &- Suche") == "Filter & Suche"


@patch("imaplib.IMAP4_SSL")
def test_imap_provider_fetch_parses_real_date_and_size(mock_imap_cls, tmp_path: Path):
    manager = ImapProfileManager(config_path=tmp_path / "imap_profiles.json")
    manager.save_profile(ImapConfig(
        profile_id="prof-1",
        account_name="GMX Postfach",
        host="imap.gmx.net",
        username="user@gmx.de",
        password="secret",
    ))
    provider = ImapMailProvider(profile_manager=manager)

    mock_imap = MagicMock()
    mock_imap_cls.return_value = mock_imap
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b"101"])

    meta_header = b'101 (RFC822.SIZE 54321 INTERNALDATE "15-May-2024 14:30:00 +0200" FLAGS (\\Seen) RFC822.HEADER {120}'
    raw_header = (
        b"From: Max Mustermann <max@example.com>\r\n"
        b"Subject: Wichtige Unterlagen\r\n"
        b"Date: Wed, 15 May 2024 12:30:00 +0000\r\n"
        b"\r\n"
    )
    mock_imap.fetch.return_value = ("OK", [(meta_header, raw_header), b")"])

    emails = provider.fetch_emails("prof-1", ["INBOX"])
    assert len(emails) == 1
    mail = emails[0]
    assert mail.size_bytes == 54321
    assert mail.received_time.year == 2024
    assert mail.received_time.month == 5
    assert mail.sender_name == "Max Mustermann"
    assert mail.sender_email == "max@example.com"

