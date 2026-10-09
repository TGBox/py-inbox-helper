"""Tests for ActionPlanner and Dry-Run planning."""
from datetime import datetime, timezone
import pytest

from py_inbox_helper.models import EmailItem, EmailCategory, ActionType
from py_inbox_helper.planner import ActionPlanner, PlannerPresetConfig


def make_categorized_email(category: EmailCategory, year: int = 2025, has_unsub: bool = False) -> EmailItem:
    recv_time = datetime(year, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    headers = {"List-Unsubscribe": "<https://unsub.com>"} if has_unsub else {}
    return EmailItem(
        id=f"item-{category.value}",
        entry_id=f"entry-{category.value}",
        store_id="store-1",
        account_name="user@test.de",
        subject=f"Subject for {category.value}",
        sender_name="Sender",
        sender_email="sender@mail.de",
        received_time=recv_time,
        is_read=False,
        headers=headers,
        assigned_category=category,
        classification_reason="Heuristics match",
    )


def test_planner_generates_default_preset_actions():
    planner = ActionPlanner(config=PlannerPresetConfig())
    emails = [
        make_categorized_email(EmailCategory.NEWSLETTER, has_unsub=True),
        make_categorized_email(EmailCategory.INVOICE_FINANCE),
        make_categorized_email(EmailCategory.NOTIFICATION),
        make_categorized_email(EmailCategory.IMPORTANT_ACTION),
        make_categorized_email(EmailCategory.RESUBMISSION),
        make_categorized_email(EmailCategory.ARCHIVE_OLD, year=2024),
    ]

    plan = planner.create_plan("user@test.de", emails)
    assert plan.total_count == 6

    # Newsletter
    n_act = next(a for a in plan.actions if "NEWSLETTER" in a.email_id)
    assert n_act.target_folder == "04_Newsletter"
    assert n_act.mark_as_read is True
    assert n_act.unsubscribe is True

    # Invoice
    i_act = next(a for a in plan.actions if "INVOICE_FINANCE" in a.email_id)
    assert i_act.target_folder == "03_Rechnungen & Finanzen"

    # Archive with year
    a_act = next(a for a in plan.actions if "ARCHIVE_OLD" in a.email_id)
    assert a_act.target_folder == "06_Archiv/2024"


def test_planner_dry_run_simulation():
    planner = ActionPlanner()
    emails = [make_categorized_email(EmailCategory.NEWSLETTER, has_unsub=True)]
    plan = planner.create_plan("user@test.de", emails)

    results = planner.simulate_dry_run(plan)
    assert len(results) == 1
    assert results[0].is_dry_run is True
    assert results[0].success is True
    assert "Simuliert:" in results[0].message
