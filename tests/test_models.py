"""Tests for core email data models."""
from datetime import datetime, timezone
import pytest

from py_inbox_helper.models import (
    EmailItem,
    EmailCategory,
    PlannedAction,
    ActionType,
    ActionPlan,
    BackupSnapshot,
    ExecutionResult,
)


def test_email_item_creation():
    now = datetime.now(timezone.utc)
    email = EmailItem(
        id="item-123",
        entry_id="ENTRY-123",
        store_id="STORE-1",
        account_name="user@example.com",
        subject="Monthly Newsletter",
        sender_name="Newsletter Team",
        sender_email="news@marketing.example.com",
        received_time=now,
        body_preview="Check out our latest news and updates...",
        is_read=False,
        importance="normal",
        categories=[],
        folder_path="Posteingang",
        size_bytes=15000,
        headers={
            "List-Unsubscribe": "<mailto:unsub@example.com>, <https://example.com/unsub?id=123>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    )

    assert email.id == "item-123"
    assert email.subject == "Monthly Newsletter"
    assert email.is_read is False
    assert email.has_unsubscribe_header is True
    assert email.unsubscribe_url == "https://example.com/unsub?id=123"
    assert email.unsubscribe_mailto == "mailto:unsub@example.com"
    assert email.is_one_click_unsubscribe is True


def test_planned_action_serialization():
    action = PlannedAction(
        email_id="item-123",
        email_subject="Monthly Newsletter",
        action_type=ActionType.MOVE_AND_MARK_READ,
        target_folder="04_Newsletter",
        mark_as_read=True,
        unsubscribe=True,
        unsubscribe_url="https://example.com/unsub?id=123",
    )

    data = action.to_dict()
    assert data["email_id"] == "item-123"
    assert data["action_type"] == "MOVE_AND_MARK_READ"
    assert data["target_folder"] == "04_Newsletter"
    assert data["mark_as_read"] is True
    assert data["unsubscribe"] is True

    restored = PlannedAction.from_dict(data)
    assert restored.email_id == action.email_id
    assert restored.action_type == action.action_type
    assert restored.target_folder == action.target_folder


def test_email_item_normalizes_naive_datetime_to_utc():
    from py_inbox_helper.models import ensure_utc

    naive_dt = datetime(2023, 6, 15, 14, 30, 0)  # No tzinfo
    email = EmailItem(
        id="item-naive",
        entry_id="ENTRY-naive",
        store_id="STORE-1",
        account_name="user@example.com",
        subject="Naive Date Test",
        sender_name="Sender",
        sender_email="sender@example.com",
        received_time=naive_dt,
    )

    # EmailItem should automatically normalize to UTC
    assert email.received_time.tzinfo is not None
    assert email.received_time.tzinfo == timezone.utc

    # ensure_utc helper directly
    assert ensure_utc(None) is None
    assert ensure_utc(naive_dt).tzinfo == timezone.utc
    aware_dt = datetime(2023, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
    assert ensure_utc(aware_dt) == aware_dt

