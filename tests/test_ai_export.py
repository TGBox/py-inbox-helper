"""Tests for the AI-ready Markdown export."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from py_inbox_helper.ai_export import build_ai_export, export_for_ai, plain_text
from py_inbox_helper.models import EmailCategory, EmailItem


def _mail(idx: int, sender: str, category: EmailCategory, **kwargs) -> EmailItem:
    defaults = dict(
        id=f"m{idx}",
        entry_id=f"e{idx}",
        store_id="acc",
        account_name="test@example.com",
        subject=f"Betreff {idx}",
        sender_name=sender.split("@")[0],
        sender_email=sender,
        received_time=datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=idx),
        assigned_category=category,
        classification_reason=f"Grund {idx}",
    )
    defaults.update(kwargs)
    return EmailItem(**defaults)


def test_export_contains_overview_and_entries():
    emails = [
        _mail(1, "news@shop.de", EmailCategory.NEWSLETTER, body_text="Angebot " * 200),
        _mail(2, "news@shop.de", EmailCategory.NEWSLETTER, is_read=True),
        _mail(3, "chef@firma.de", EmailCategory.IMPORTANT_ACTION, is_protected=True, body_text="Bitte bis Freitag."),
    ]
    md = build_ai_export(emails, account_name="Testkonto", notes="Mein Scan", body_limit=100)

    assert "Postfach: Testkonto" in md
    assert "Anzahl E-Mails: 3" in md
    assert "| Newsletter & Promo | 2 | 1 |" in md
    assert "| news@shop.de | 2 | Newsletter & Promo |" in md
    assert "Geschützte Absender (VIP/Whitelist): 1" in md
    # Newest first
    assert md.index("Betreff 3") < md.index("Betreff 1")
    assert "Kategorie: Wichtig / Aktion – Grund 3" in md
    assert "Text: Bitte bis Freitag." in md
    # Long bodies are truncated
    assert "[…]" in md


def test_export_without_body_omits_text():
    md = build_ai_export([_mail(1, "a@b.de", EmailCategory.JUNK, body_text="geheim")], include_body=False)
    assert "geheim" not in md
    assert "- Text:" not in md
    assert "Mail-Text enthalten: nein" in md


def test_plain_text_strips_html_when_no_text():
    mail = _mail(1, "a@b.de", EmailCategory.NOTIFICATION, body_html="<style>x{}</style><p>Hallo&nbsp;<b>Welt</b></p>")
    assert plain_text(mail) == "Hallo Welt"


def test_export_for_ai_writes_file(tmp_path: Path):
    target = export_for_ai([_mail(1, "a@b.de", EmailCategory.NEWSLETTER)], tmp_path / "out" / "export.md")
    assert target.read_text(encoding="utf-8").startswith("# Postfach-Analyse")


def test_export_handles_empty_list():
    md = build_ai_export([])
    assert "Anzahl E-Mails: 0" in md
