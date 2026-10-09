"""Tests for SenderCluster and StorageAnalyzer."""
from datetime import datetime, timezone
import pytest

from py_inbox_helper.models import EmailItem
from py_inbox_helper.storage import StorageAnalyzer, SenderCluster, format_bytes


def make_sized_email(sender: str, name: str, size: int, unread: bool = True, has_unsub: bool = False) -> EmailItem:
    headers = {"List-Unsubscribe": "<https://unsub.com>"} if has_unsub else {}
    return EmailItem(
        id=f"item-{sender}-{size}",
        entry_id=f"entry-{sender}-{size}",
        store_id="store-1",
        account_name="user@test.de",
        subject=f"Mail from {name}",
        sender_name=name,
        sender_email=sender,
        received_time=datetime.now(timezone.utc),
        is_read=not unread,
        size_bytes=size,
        headers=headers,
    )


def test_sender_clustering():
    emails = [
        make_sized_email("news@shop.de", "Shop", 1000, unread=True, has_unsub=True),
        make_sized_email("news@shop.de", "Shop", 2000, unread=True, has_unsub=True),
        make_sized_email("news@shop.de", "Shop", 3000, unread=False, has_unsub=True),
        make_sized_email("colleague@work.de", "Colleague", 500000, unread=True),
    ]

    analyzer = StorageAnalyzer()
    clusters = analyzer.cluster_by_sender(emails)

    assert len(clusters) == 2
    # First cluster should be shop (3 emails)
    top = clusters[0]
    assert top.sender_email == "news@shop.de"
    assert top.email_count == 3
    assert top.unread_count == 2
    assert top.total_size_bytes == 6000
    assert top.has_unsubscribe is True
    assert len(top.email_ids) == 3


def test_filter_large_emails():
    emails = [
        make_sized_email("a@b.com", "Small", 500_000),      # ~500 KB
        make_sized_email("c@d.com", "Medium", 6_000_000),   # ~6 MB
        make_sized_email("e@f.com", "Large", 25_000_000),   # ~25 MB
    ]

    analyzer = StorageAnalyzer()
    # Filter > 5 MB
    large_5mb = analyzer.get_large_emails(emails, min_bytes=5_000_000)
    assert len(large_5mb) == 2
    assert large_5mb[0].size_bytes == 25_000_000  # Sorted descending by size

    # Format bytes helper
    assert format_bytes(500) == "500 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(5_242_880) == "5.0 MB"
