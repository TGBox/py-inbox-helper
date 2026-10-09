"""Action planning and dry-run execution engine with configurable presets."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from py_inbox_helper.models import (
    ActionPlan,
    ActionType,
    EmailCategory,
    EmailItem,
    ExecutionResult,
    PlannedAction,
)


@dataclass
class CategoryRulePreset:
    """Action rules configured for a specific email category."""
    target_folder: Optional[str]
    mark_as_read: bool = False
    mark_as_unread: bool = False
    set_flag: Optional[str] = None
    add_category: Optional[str] = None
    offer_unsubscribe: bool = False
    use_year_subfolder: bool = False


@dataclass
class PlannerPresetConfig:
    """Smart default folder presets and rules."""
    category_rules: Dict[EmailCategory, CategoryRulePreset] = field(default_factory=lambda: {
        EmailCategory.NEWSLETTER: CategoryRulePreset(
            target_folder="04_Newsletter",
            mark_as_read=True,
            offer_unsubscribe=True,
        ),
        EmailCategory.INVOICE_FINANCE: CategoryRulePreset(
            target_folder="03_Rechnungen & Finanzen",
            mark_as_read=False,
            add_category="Rechnung/Finanzen",
        ),
        EmailCategory.NOTIFICATION: CategoryRulePreset(
            target_folder="05_Benachrichtigungen",
            mark_as_read=True,
        ),
        EmailCategory.IMPORTANT_ACTION: CategoryRulePreset(
            target_folder="02_Wichtig",
            mark_as_read=False,
            set_flag="Follow up",
            add_category="Wichtig",
        ),
        EmailCategory.RESUBMISSION: CategoryRulePreset(
            target_folder="01_Wiedervorlage",
            mark_as_read=False,
            set_flag="Wiedervorlage",
            add_category="Wiedervorlage",
        ),
        EmailCategory.ARCHIVE_OLD: CategoryRulePreset(
            target_folder="06_Archiv",
            mark_as_read=True,
            use_year_subfolder=True,
        ),
        EmailCategory.JUNK: CategoryRulePreset(
            target_folder="Gelöschte Elemente",
            mark_as_read=True,
        ),
        EmailCategory.UNCLASSIFIED: CategoryRulePreset(
            target_folder=None,  # Leave in place
            mark_as_read=False,
        ),
    })


class ActionPlanner:
    """Builds action plans based on email classification and simulates dry-runs."""

    def __init__(self, config: Optional[PlannerPresetConfig] = None):
        self.config = config or PlannerPresetConfig()

    def create_plan(self, account_name: str, emails: List[EmailItem]) -> ActionPlan:
        """Transforms categorized emails into planned actions."""
        plan = ActionPlan(account_name=account_name)

        for email in emails:
            cat = email.assigned_category
            rule = self.config.category_rules.get(cat, self.config.category_rules[EmailCategory.UNCLASSIFIED])

            target_folder = rule.target_folder
            if target_folder and rule.use_year_subfolder:
                year_str = str(email.received_time.year)
                target_folder = f"{target_folder}/{year_str}"

            action_type = ActionType.NONE
            if target_folder:
                if rule.mark_as_read:
                    action_type = ActionType.MOVE_AND_MARK_READ
                else:
                    action_type = ActionType.MOVE
            elif rule.mark_as_read:
                action_type = ActionType.MARK_READ
            elif rule.mark_as_unread:
                action_type = ActionType.MARK_UNREAD

            unsub = rule.offer_unsubscribe and email.has_unsubscribe_header

            action = PlannedAction(
                email_id=email.id,
                email_subject=email.subject,
                action_type=action_type,
                target_folder=target_folder,
                mark_as_read=rule.mark_as_read,
                mark_as_unread=rule.mark_as_unread,
                set_flag=rule.set_flag,
                add_category=rule.add_category,
                unsubscribe=unsub,
                unsubscribe_url=email.unsubscribe_url if unsub else None,
                unsubscribe_mailto=email.unsubscribe_mailto if unsub else None,
                explanation=f"Kategorie: {cat.value} ({email.classification_reason})",
                is_enabled=True,
            )
            plan.actions.append(action)

        return plan

    def simulate_dry_run(self, plan: ActionPlan) -> List[ExecutionResult]:
        """Simulates all actions without mutating any real data, generating verification results."""
        results: List[ExecutionResult] = []
        for action in plan.actions:
            if not action.is_enabled:
                results.append(ExecutionResult(
                    action=action,
                    success=True,
                    is_dry_run=True,
                    message="Übersprungen (Deaktiviert durch Benutzer)",
                ))
                continue

            desc_parts = []
            if action.target_folder:
                desc_parts.append(f"Verschieben nach '{action.target_folder}'")
            if action.mark_as_read:
                desc_parts.append("Als gelesen markieren")
            if action.set_flag:
                desc_parts.append(f"Kennzeichnung setzen ('{action.set_flag}')")
            if action.add_category:
                desc_parts.append(f"Kategorie '{action.add_category}' zuweisen")
            if action.unsubscribe:
                desc_parts.append("Newsletter-Abmeldung vorbereiten")

            desc = ", ".join(desc_parts) if desc_parts else "Keine Änderung"
            results.append(ExecutionResult(
                action=action,
                success=True,
                is_dry_run=True,
                message=f"Simuliert: {desc}",
            ))

        return results
