"""Tests for ImapMailProvider and connection profile manager."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from py_inbox_helper.models import ActionType, PlannedAction
from py_inbox_helper.provider.imap_provider import (
    ImapConfig,
    ImapMailProvider,
    ImapProfileManager,
    decode_imap_utf7,
    encode_imap_utf7,
)
from fake_imap_server import FakeImapServer


def make_headers(subject: str, message_id: str, sender: str = "Max Mustermann <max@example.com>") -> bytes:
    return (
        f"From: {sender}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: <{message_id}@example.com>\r\n"
        "Date: Wed, 15 May 2024 12:30:00 +0000\r\n"
        "\r\n"
    ).encode()


@pytest.fixture
def server():
    srv = FakeImapServer()
    srv.add_mailbox("Trash", "\\HasNoChildren \\Trash")
    yield srv
    srv.stop()


def make_provider(server: FakeImapServer, tmp_path: Path) -> ImapMailProvider:
    manager = ImapProfileManager(config_path=tmp_path / "imap_profiles.json")
    manager.save_profile(ImapConfig(
        profile_id="prof-1",
        account_name="Testpostfach",
        host="127.0.0.1",
        port=server.port,
        use_ssl=False,
        username="user@example.com",
        password="secret",
    ))
    return ImapMailProvider(profile_manager=manager)


def move_action(email, target: str, mark_as_read: bool = False) -> PlannedAction:
    return PlannedAction(
        email_id=email.id,
        email_subject=email.subject,
        action_type=ActionType.MOVE,
        target_folder=target,
        mark_as_read=mark_as_read,
    )


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
        b'(\\Noselect \\HasChildren) "/" "[Gmail]"',
    ])

    folders = provider.list_folders("prof-1")
    assert len(folders) == 2  # the non-selectable container folder is skipped
    assert any(f.name == "INBOX" and f.is_inbox for f in folders)


def test_imap_utf7_roundtrip():
    assert decode_imap_utf7("Entw&APw-rfe") == "Entwürfe"
    assert decode_imap_utf7("Gel&APY-scht") == "Gelöscht"
    assert decode_imap_utf7("Posteingang") == "Posteingang"
    assert decode_imap_utf7("Filter &- Suche") == "Filter & Suche"

    assert encode_imap_utf7("Entwürfe") == "Entw&APw-rfe"
    assert encode_imap_utf7("Filter & Suche") == "Filter &- Suche"
    for name in ["Gelöschte Elemente", "03_Rechnungen & Finanzen", "06_Archiv/2024", "日本語"]:
        assert decode_imap_utf7(encode_imap_utf7(name)) == name


def test_fetch_parses_metadata_and_uses_uids(server, tmp_path: Path):
    server.add_message("INBOX", make_headers("Alt", "m1"), flags=["\\Seen"], size=54321)
    server.add_message("INBOX", make_headers("Neu", "m2"))
    provider = make_provider(server, tmp_path)

    emails = provider.fetch_emails("prof-1", ["INBOX"])
    assert [e.subject for e in emails] == ["Neu", "Alt"]  # newest first

    old = emails[1]
    assert old.entry_id == "1"  # the UID, not a sequence number
    assert old.id == f"prof-1_INBOX_{server.uidvalidity['INBOX']}-1"
    assert old.size_bytes == 54321
    assert old.is_read is True
    assert emails[0].is_read is False
    assert old.received_time.year == 2024 and old.received_time.month == 5
    assert old.sender_name == "Max Mustermann"
    assert old.sender_email == "max@example.com"
    # Scanning must not change anything on the server
    assert server.mailboxes["INBOX"][2]["flags"] == set()


def test_fetch_reports_login_failure(server, tmp_path: Path):
    server.password = "something-else"
    provider = make_provider(server, tmp_path)
    with pytest.raises(RuntimeError, match="Anmeldung"):
        provider.fetch_emails("prof-1", ["INBOX"])


def test_execute_moves_the_right_messages(server, tmp_path: Path):
    """Regression: actions used sequence numbers, which shift after every move."""
    for i in range(1, 6):
        server.add_message("INBOX", make_headers(f"Mail {i}", f"m{i}"))
    provider = make_provider(server, tmp_path)
    emails = {e.subject: e for e in provider.fetch_emails("prof-1", ["INBOX"])}

    first = provider.execute_action(move_action(emails["Mail 1"], "04_Newsletter", mark_as_read=True), "prof-1")
    second = provider.execute_action(move_action(emails["Mail 4"], "04_Newsletter"), "prof-1")
    provider.close()

    assert first.success and second.success, (first.message, second.message)
    assert server.subjects("INBOX") == ["Mail 2", "Mail 3", "Mail 5"]
    assert server.subjects("04_Newsletter") == ["Mail 1", "Mail 4"]
    assert "\\Seen" in server.mailboxes["04_Newsletter"][1]["flags"]
    assert "\\Seen" not in server.mailboxes["04_Newsletter"][2]["flags"]
    # New location is reported for the backup snapshot
    assert (first.new_folder, first.new_entry_id) == ("04_Newsletter", "1")
    assert (second.new_folder, second.new_entry_id) == ("04_Newsletter", "2")
    # One connection for the whole run, never a folder-wide EXPUNGE
    assert sum(1 for c in server.commands if c.startswith("LOGIN")) == 2  # scan + execution
    assert "EXPUNGE" not in server.commands


def test_execute_creates_encoded_target_folder_and_uses_real_trash(server, tmp_path: Path):
    server.add_message("INBOX", make_headers("Rechnung", "m1"))
    server.add_message("INBOX", make_headers("Spam", "m2"))
    provider = make_provider(server, tmp_path)
    emails = {e.subject: e for e in provider.fetch_emails("prof-1", ["INBOX"])}

    res1 = provider.execute_action(move_action(emails["Rechnung"], "03_Rechnungen & Finanzen"), "prof-1")
    res2 = provider.execute_action(move_action(emails["Spam"], "Gelöschte Elemente"), "prof-1")
    provider.close()

    assert res1.success and res2.success, (res1.message, res2.message)
    assert server.subjects("03_Rechnungen &- Finanzen") == ["Rechnung"]
    assert server.subjects("Trash") == ["Spam"]
    assert "Gel&APY-schte Elemente" not in server.mailboxes  # no look-alike trash folder created


def test_execute_without_move_and_uidplus_keeps_other_deleted_mails(server, tmp_path: Path):
    server.capabilities = ["IMAP4rev1"]
    server.add_message("INBOX", make_headers("Vom Nutzer als gelöscht markiert", "m1"), flags=["\\Deleted"])
    server.add_message("INBOX", make_headers("Newsletter", "m2"))
    provider = make_provider(server, tmp_path)
    emails = {e.subject: e for e in provider.fetch_emails("prof-1", ["INBOX"])}

    res = provider.execute_action(move_action(emails["Newsletter"], "04_Newsletter"), "prof-1")
    provider.close()

    assert res.success, res.message
    assert server.subjects("04_Newsletter") == ["Newsletter"]
    assert res.new_entry_id == "1"  # found via Message-ID search
    # The user's own \Deleted message must not be purged by our action
    assert "Vom Nutzer als gelöscht markiert" in server.subjects("INBOX")
    assert "\\Deleted" in server.mailboxes["INBOX"][2]["flags"]


def test_execute_does_not_delete_when_copy_is_rejected(server, tmp_path: Path):
    server.capabilities = ["IMAP4rev1", "UIDPLUS"]
    server.add_mailbox("04_Newsletter")
    server.add_message("INBOX", make_headers("Newsletter", "m1"))
    provider = make_provider(server, tmp_path)
    email = provider.fetch_emails("prof-1", ["INBOX"])[0]

    server.reject_copy = True
    res = provider.execute_action(move_action(email, "04_Newsletter"), "prof-1")
    provider.close()

    assert res.success is False
    assert "NICHT gelöscht" in res.message
    assert server.subjects("INBOX") == ["Newsletter"]
    assert "\\Deleted" not in server.mailboxes["INBOX"][1]["flags"]


def test_execute_rejects_stale_or_legacy_ids(server, tmp_path: Path):
    server.add_message("INBOX", make_headers("Mail", "m1"))
    provider = make_provider(server, tmp_path)
    email = provider.fetch_emails("prof-1", ["INBOX"])[0]

    # Id format of older versions (sequence number, no UIDVALIDITY)
    legacy = PlannedAction(email_id="prof-1_INBOX_1", email_subject="x", target_folder="04_Newsletter")
    res = provider.execute_action(legacy, "prof-1")
    assert res.success is False and "neu scannen" in res.message

    # Message vanished since the scan
    del server.mailboxes["INBOX"][1]
    res = provider.execute_action(move_action(email, "04_Newsletter"), "prof-1")
    provider.close()
    assert res.success is False and "neu scannen" in res.message
    assert "04_Newsletter" not in server.mailboxes or server.subjects("04_Newsletter") == []


def test_restore_moves_message_back_and_resets_read_state(server, tmp_path: Path):
    server.add_message("INBOX", make_headers("Bleibt", "m1"))
    server.add_message("INBOX", make_headers("Newsletter", "m2"))
    provider = make_provider(server, tmp_path)
    email = next(e for e in provider.fetch_emails("prof-1", ["INBOX"]) if e.subject == "Newsletter")

    res = provider.execute_action(move_action(email, "04_Newsletter", mark_as_read=True), "prof-1")
    assert res.success, res.message
    assert server.subjects("INBOX") == ["Bleibt"]

    new_uid = provider.restore_item(
        entry_id=res.new_entry_id,
        store_id="prof-1",
        target_folder=email.folder_path,
        is_read=False,
        categories=[],
        current_folder=res.new_folder,
    )
    provider.close()

    assert server.subjects("04_Newsletter") == []
    assert server.subjects("INBOX") == ["Bleibt", "Newsletter"]
    assert new_uid == "3"
    assert "\\Seen" not in server.mailboxes["INBOX"][3]["flags"]


def test_restore_fails_loudly_when_message_is_gone(server, tmp_path: Path):
    provider = make_provider(server, tmp_path)
    with pytest.raises(Exception, match="nicht mehr gefunden"):
        provider.restore_item(entry_id="99", store_id="prof-1", target_folder="INBOX", is_read=True, categories=[])
    provider.close()
