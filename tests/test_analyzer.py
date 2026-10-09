"""Tests for email classification and heuristic rule analyzer."""
from datetime import datetime, timedelta, timezone
import pytest

from py_inbox_helper.models import EmailItem, EmailCategory
from py_inbox_helper.analyzer import EmailAnalyzer, RuleConfig


def make_email(
    subject: str,
    sender_name: str = "Test Sender",
    sender_email: str = "sender@example.com",
    body: str = "",
    days_ago: int = 10,
    headers: dict = None,
    importance: str = "normal",
) -> EmailItem:
    recv_time = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return EmailItem(
        id=f"item-{subject}",
        entry_id=f"entry-{subject}",
        store_id="store-1",
        account_name="test@domain.com",
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        received_time=recv_time,
        body_preview=body,
        is_read=False,
        importance=importance,
        categories=[],
        folder_path="Posteingang",
        headers=headers or {},
    )


def test_classify_newsletter_by_header():
    analyzer = EmailAnalyzer()
    email = make_email(
        subject="Wöchentliche Angebote",
        headers={"List-Unsubscribe": "<https://shop.example.com/unsub>"},
    )
    category, reason = analyzer.classify(email)
    assert category == EmailCategory.NEWSLETTER
    assert "List-Unsubscribe" in reason


def test_classify_newsletter_by_keywords():
    analyzer = EmailAnalyzer()
    email = make_email(
        subject="Unser Sommer-Newsletter: 20% Rabatt auf alles!",
        sender_email="marketing@brand.com",
    )
    category, reason = analyzer.classify(email)
    assert category == EmailCategory.NEWSLETTER


def test_classify_invoice_finance():
    analyzer = EmailAnalyzer()
    email = make_email(
        subject="Ihre Rechnung Nr. 2026-44912 zur Bestellung",
        sender_email="buchhaltung@firma.de",
    )
    category, reason = analyzer.classify(email)
    assert category == EmailCategory.INVOICE_FINANCE


def test_classify_notification():
    analyzer = EmailAnalyzer()
    email = make_email(
        subject="Sicherheitswarnung: Neuer Login von unbekanntem Gerät",
        sender_email="no-reply@auth.service.com",
    )
    category, reason = analyzer.classify(email)
    assert category == EmailCategory.NOTIFICATION


def test_classify_important_action():
    analyzer = EmailAnalyzer()
    email = make_email(
        subject="Dringend: Bitte um Rückmeldung bis Freitag",
        importance="high",
    )
    category, reason = analyzer.classify(email)
    assert category == EmailCategory.IMPORTANT_ACTION


def test_classify_archive_old():
    # 400 days old email without other strong signals
    analyzer = EmailAnalyzer(RuleConfig(archive_days_threshold=365))
    email = make_email(
        subject="Kaffeepause am Mittwoch",
        sender_email="kollege@firma.de",
        days_ago=400,
    )
    category, reason = analyzer.classify(email)
    assert category == EmailCategory.ARCHIVE_OLD
    assert "Alter" in reason or "Tage" in reason


def test_classify_vip_whitelist_sender():
    config = RuleConfig(whitelist_senders=["chef@unternehmen.de", "@familie.de"])
    analyzer = EmailAnalyzer(config)

    # Direct match on email
    email1 = make_email(
        subject="Wochenbericht & Update",
        sender_email="chef@unternehmen.de",
        days_ago=500,  # Even if very old, VIP takes precedence!
    )
    cat1, reason1 = analyzer.classify(email1)
    assert cat1 == EmailCategory.IMPORTANT_ACTION
    assert "Whitelist" in reason1

    # Domain match
    email2 = make_email(
        subject="Familientreffen am Sonntag",
        sender_email="mama@familie.de",
        days_ago=250,
    )
    cat2, reason2 = analyzer.classify(email2)
    assert cat2 == EmailCategory.IMPORTANT_ACTION
    assert "Whitelist" in reason2

