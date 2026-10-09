"""Email analysis engine with extensible classifier architecture."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import re

from py_inbox_helper.models import EmailCategory, EmailItem, ensure_utc


@dataclass
class RuleConfig:
    """Configurable rules and thresholds for email classification."""
    archive_days_threshold: int = 180
    newsletter_keywords: List[str] = field(default_factory=lambda: [
        "newsletter", "abmelden", "unsubscribe", "rabatt", "gutschein",
        "sale", "angebote", "sonderangebot", "weekly digest", "daily digest"
    ])
    invoice_keywords: List[str] = field(default_factory=lambda: [
        "rechnung", "invoice", "beleg", "zahlungsbestätigung", "kontoauszug",
        "abrechnung", "bestellbestätigung", "quittung", "tax invoice"
    ])
    notification_keywords: List[str] = field(default_factory=lambda: [
        "sicherheitswarnung", "neuer login", "passwort zurücksetzen", "verifizierungscode",
        "benachrichtigung", "notification", "security alert", "status update"
    ])
    important_keywords: List[str] = field(default_factory=lambda: [
        "dringend", "urgent", "wichtig", "frist", "deadline", "aktion erforderlich",
        "action required", "bitte um rückmeldung", "terminbestätigung"
    ])
    resubmission_keywords: List[str] = field(default_factory=lambda: [
        "wiedervorlage", "reminder", "nachfassen", "follow up", "follow-up", "erinnerung"
    ])
    junk_keywords: List[str] = field(default_factory=lambda: [
        "viagra", "casino", "lottery", "gewinnspiel", "krypto-gewinn", "bitcoin profit"
    ])
    whitelist_senders: List[str] = field(default_factory=list)


class BaseEmailClassifier(ABC):
    """Abstract interface for email classifiers (heuristics, rule-engine, AI/LLM models)."""

    @abstractmethod
    def classify(self, email: EmailItem) -> Tuple[EmailCategory, str]:
        """Classifies an email and returns (Category, Reason)."""
        pass


class EmailAnalyzer(BaseEmailClassifier):
    """Heuristic rule-based analyzer for classifying neglected inbox emails."""

    def __init__(self, config: Optional[RuleConfig] = None):
        self.config = config or RuleConfig()

    def classify(self, email: EmailItem) -> Tuple[EmailCategory, str]:
        sender = (email.sender_email or "").lower()
        sender_name = (email.sender_name or "").lower()
        subject = (email.subject or "").lower()
        preview = (email.body_preview or "").lower()
        combined_text = f"{subject} {preview}"

        # 0. VIP & Whitelist Protection (Takes highest priority)
        for wl in self.config.whitelist_senders:
            clean_wl = wl.strip().lower()
            if clean_wl and (clean_wl in sender or (clean_wl.startswith("@") and sender.endswith(clean_wl))):
                return EmailCategory.IMPORTANT_ACTION, f"Geschützter VIP-/Whitelist-Absender ({sender})"

        # 1. High importance or explicit action required
        if email.importance.lower() == "high":
            return EmailCategory.IMPORTANT_ACTION, "Als wichtig markiert (Hohe Priorität)"

        for kw in self.config.important_keywords:
            if kw in subject:
                return EmailCategory.IMPORTANT_ACTION, f"Wichtiges Signal im Betreff gefunden: '{kw}'"

        # 2. Resubmission / Wiedervorlage / Follow-up
        for kw in self.config.resubmission_keywords:
            if kw in subject:
                return EmailCategory.RESUBMISSION, f"Wiedervorlage-Signal im Betreff gefunden: '{kw}'"

        # 3. Invoice & Finance
        for kw in self.config.invoice_keywords:
            if kw in subject:
                return EmailCategory.INVOICE_FINANCE, f"Rechnungs-/Finanzbegriff im Betreff: '{kw}'"

        # 4. Obvious Junk / Spam
        for kw in self.config.junk_keywords:
            if kw in subject or kw in preview:
                return EmailCategory.JUNK, f"Unerwünschte Werbe-Schlagwörter gefunden: '{kw}'"

        # 5. Newsletters & Marketing
        if email.has_unsubscribe_header:
            return EmailCategory.NEWSLETTER, "Header 'List-Unsubscribe' vorhanden"

        for kw in self.config.newsletter_keywords:
            if kw in subject:
                return EmailCategory.NEWSLETTER, f"Newsletter-Schlagwort im Betreff: '{kw}'"

        if "marketing" in sender or "promo" in sender or "newsletter" in sender or "news@" in sender:
            return EmailCategory.NEWSLETTER, f"Marketing-Absenderadresse erkannt: '{sender}'"

        # 6. Automated Notifications & System alerts
        if "no-reply" in sender or "noreply" in sender or "donotreply" in sender:
            # Check if it was an invoice already handled above; otherwise it's a notification
            return EmailCategory.NOTIFICATION, f"Automatisierte Absenderadresse (No-Reply): '{sender}'"

        for kw in self.config.notification_keywords:
            if kw in subject:
                return EmailCategory.NOTIFICATION, f"Benachrichtigungs-Signal im Betreff: '{kw}'"

        # 7. Age-based Archiving
        recv_time = ensure_utc(email.received_time) or datetime.now(timezone.utc)
        age_days = (datetime.now(timezone.utc) - recv_time).days
        if age_days >= self.config.archive_days_threshold:
            return EmailCategory.ARCHIVE_OLD, f"Alter der E-Mail beträgt {age_days} Tage (Schwelle: {self.config.archive_days_threshold} Tage)"

        # Fallback
        return EmailCategory.UNCLASSIFIED, "Keine spezifische Regel zutreffend"

    def analyze_batch(self, emails: List[EmailItem]) -> List[EmailItem]:
        """Analyzes a batch of emails and mutates their assigned categories and reasons."""
        for email in emails:
            cat, reason = self.classify(email)
            email.assigned_category = cat
            email.classification_reason = reason
        return emails
