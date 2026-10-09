"""Tests for unsubscribe extraction and handler."""
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from py_inbox_helper.models import EmailItem
from py_inbox_helper.unsubscribe import UnsubscribeManager, UnsubscribeResult


def make_email_with_headers(headers: dict) -> EmailItem:
    return EmailItem(
        id="item-test",
        entry_id="entry-1",
        store_id="store-1",
        account_name="user@test.de",
        subject="Werbe-Newsletter",
        sender_name="Shop",
        sender_email="promo@shop.de",
        received_time=datetime.now(timezone.utc),
        headers=headers,
    )


def test_unsubscribe_manager_extracts_info():
    email = make_email_with_headers({
        "List-Unsubscribe": "<mailto:unsub@shop.de?subject=unsubscribe>, <https://shop.de/unsub?token=abc>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    })
    manager = UnsubscribeManager()
    info = manager.inspect_email(email)

    assert info.has_unsubscribe is True
    assert info.is_one_click is True
    assert info.http_url == "https://shop.de/unsub?token=abc"
    assert info.mailto_uri == "mailto:unsub@shop.de?subject=unsubscribe"


@patch("requests.post")
def test_unsubscribe_one_click_execution(mock_post):
    mock_post.return_value = MagicMock(status_code=200, text="OK")

    email = make_email_with_headers({
        "List-Unsubscribe": "<https://shop.de/unsub?token=abc>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    })
    manager = UnsubscribeManager()
    result = manager.execute_unsubscribe(email)

    assert result.success is True
    assert "Erfolgreich abgemeldet" in result.message
    mock_post.assert_called_once_with(
        "https://shop.de/unsub?token=abc",
        data={"List-Unsubscribe": "One-Click"},
        timeout=10,
        headers={"User-Agent": "PyInboxHelper/0.1.6"},
    )
