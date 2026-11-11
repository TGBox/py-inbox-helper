"""Email analysis engine with extensible classifier architecture."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import json
import logging
from pathlib import Path
import re
from typing import List, Optional, Tuple

from py_inbox_helper.models import EmailCategory, EmailItem, ensure_utc

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1024)
def _keyword_pattern(keyword: str) -> Optional[re.Pattern]:
    kw = keyword.strip().lower()
    core = kw.strip("*")
    if not core:
        return None
    prefix = "" if kw.startswith("*") else r"(?<!\w)"
    suffix = "" if kw.endswith("*") else r"(?!\w)"
    return re.compile(prefix + re.escape(core) + suffix)


def keyword_matches(keyword: str, text: str) -> bool:
    """Checks whether ``keyword`` occurs in the (lower-cased) ``text``.

    Keywords match whole words only, so "sale" does not hit "Wholesale" and
    "frist" does not hit "unbefristet". A ``*`` at the start and/or end allows
    the keyword to be part of a longer word:

    - ``"wichtig"``     matches "Wichtig: ..."        but not "unwichtig"
    - ``"*frist"``      matches "Abgabefrist"         but not "befristet"
    - ``"rechnung*"``   matches "Rechnungsnummer"     but not "Abrechnung"
    - ``"*rechnung*"``  matches any word containing "rechnung"
    """
    pattern = _keyword_pattern(keyword)
    return bool(pattern and pattern.search(text))


def first_matching_keyword(keywords: List[str], text: str) -> Optional[str]:
    """Returns the first keyword of ``keywords`` found in ``text`` (or None)."""
    for kw in keywords:
        if keyword_matches(kw, text):
            return kw.strip().strip("*")
    return None


def default_whitelist_path() -> Path:
    return Path.home() / ".py_inbox_helper" / "whitelist.json"


def load_whitelist(path: Optional[Path] = None) -> List[str]:
    """Loads the persisted VIP / whitelist sender list (empty if none saved yet)."""
    target = Path(path) if path else default_whitelist_path()
    if not target.exists():
        return []
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [str(entry).strip() for entry in data if str(entry).strip()]
    except Exception as ex:
        logger.warning("Could not load whitelist from %s: %s", target, ex)
        return []


def save_whitelist(senders: List[str], path: Optional[Path] = None) -> None:
    """Persists the VIP / whitelist sender list so it survives a restart."""
    target = Path(path) if path else default_whitelist_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([s.strip() for s in senders if s.strip()], f, indent=2, ensure_ascii=False)
        tmp.replace(target)
    except Exception as ex:
        logger.warning("Could not save whitelist to %s: %s", target, ex)


@dataclass
class RuleConfig:
    """Configurable rules and thresholds for email classification.

    Keywords match whole words; use ``*`` as wildcard for compound words
    (see :func:`keyword_matches`).
    """
    archive_days_threshold: int = 180
    newsletter_keywords: List[str] = field(default_factory=lambda: [
        "newsletter*", "abmelden", "unsubscribe", "*rabatt*", "*gutschein*",
        "sale", "angebote", "sonderangebot*", "weekly digest", "daily digest"
    ])
    invoice_keywords: List[str] = field(default_factory=lambda: [
        "*rechnung*", "invoice*", "*beleg", "*belege", "zahlungsbestätigung", "kontoauszug*",
        "bestellbestätigung", "quittung*", "tax invoice"
    ])
    notification_keywords: List[str] = field(default_factory=lambda: [
        "sicherheitswarnung", "neuer login", "passwort zurücksetzen", "verifizierungscode",
        "benachrichtigung*", "notification*", "security alert", "status update"
    ])
    important_keywords: List[str] = field(default_factory=lambda: [
        "dringend*", "urgent", "wichtig", "wichtige*", "*frist", "*fristen", "deadline*",
        "aktion erforderlich", "action required", "bitte um rückmeldung", "terminbestätigung"
    ])
    resubmission_keywords: List[str] = field(default_factory=lambda: [
        "wiedervorlage", "reminder", "nachfassen", "follow up", "follow-up", "*erinnerung*"
    ])
    junk_keywords: List[str] = field(default_factory=lambda: [
        "viagra", "casino*", "lottery", "gewinnspiel*", "krypto-gewinn*", "bitcoin profit"
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

    def is_protected_sender(self, email: EmailItem) -> bool:
        """True if the sender is on the VIP / whitelist.

        Entries are matched as follows:
        - ``chef@firma.de``  exact address
        - ``@firma.de``      every address of that domain
        - ``firma.de``       that domain including its subdomains
        """
        sender = (email.sender_email or "").strip().lower()
        if not sender:
            return False
        domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
        for wl in self.config.whitelist_senders:
            entry = wl.strip().lower()
            if not entry:
                continue
            if entry.startswith("@"):
                if sender.endswith(entry):
                    return True
            elif "@" in entry:
                if sender == entry:
                    return True
            elif domain and (domain == entry or domain.endswith("." + entry)):
                return True
        return False

    def _is_bulk_mail(self, email: EmailItem, sender: str) -> Optional[str]:
        """Returns a reason if the mail is mass mail (newsletter / marketing), else None."""
        if email.has_unsubscribe_header:
            return "Header 'List-Unsubscribe' vorhanden"
        for key, value in email.headers.items():
            if key.lower() == "precedence" and (value or "").strip().lower() == "bulk":
                return "Header 'Precedence: bulk' vorhanden"
        if "marketing" in sender or "promo" in sender or "newsletter" in sender or "news@" in sender:
            return f"Marketing-Absenderadresse erkannt: '{sender}'"
        return None

    def classify(self, email: EmailItem) -> Tuple[EmailCategory, str]:
        sender = (email.sender_email or "").lower()
        subject = (email.subject or "").lower()
        preview = (email.body_preview or "").lower()

        # 0. VIP & Whitelist Protection (Takes highest priority)
        if self.is_protected_sender(email):
            return EmailCategory.IMPORTANT_ACTION, f"Geschützter VIP-/Whitelist-Absender ({sender})"

        # 1. Obvious Junk / Spam
        kw = first_matching_keyword(self.config.junk_keywords, f"{subject} {preview}")
        if kw:
            return EmailCategory.JUNK, f"Unerwünschte Werbe-Schlagwörter gefunden: '{kw}'"

        # 2. Mass mail (newsletter / marketing). This is checked BEFORE the subject
        #    keywords, because advertising routinely uses words like "Wichtig",
        #    "Letzte Erinnerung" or "Frist" - those must not turn ads into "important".
        bulk_reason = self._is_bulk_mail(email, sender)
        if bulk_reason:
            kw = first_matching_keyword(self.config.invoice_keywords, subject)
            if kw:
                return EmailCategory.INVOICE_FINANCE, f"Rechnungs-/Finanzbegriff im Betreff: '{kw}'"
            return EmailCategory.NEWSLETTER, bulk_reason

        # 3. High importance or explicit action required
        if (email.importance or "").lower() == "high":
            return EmailCategory.IMPORTANT_ACTION, "Als wichtig markiert (Hohe Priorität)"

        kw = first_matching_keyword(self.config.important_keywords, subject)
        if kw:
            return EmailCategory.IMPORTANT_ACTION, f"Wichtiges Signal im Betreff gefunden: '{kw}'"

        # 4. Resubmission / Wiedervorlage / Follow-up
        kw = first_matching_keyword(self.config.resubmission_keywords, subject)
        if kw:
            return EmailCategory.RESUBMISSION, f"Wiedervorlage-Signal im Betreff gefunden: '{kw}'"

        # 5. Invoice & Finance
        kw = first_matching_keyword(self.config.invoice_keywords, subject)
        if kw:
            return EmailCategory.INVOICE_FINANCE, f"Rechnungs-/Finanzbegriff im Betreff: '{kw}'"

        # 6. Newsletters & Marketing by subject
        kw = first_matching_keyword(self.config.newsletter_keywords, subject)
        if kw:
            return EmailCategory.NEWSLETTER, f"Newsletter-Schlagwort im Betreff: '{kw}'"

        # 7. Automated Notifications & System alerts
        if "no-reply" in sender or "noreply" in sender or "donotreply" in sender:
            return EmailCategory.NOTIFICATION, f"Automatisierte Absenderadresse (No-Reply): '{sender}'"

        kw = first_matching_keyword(self.config.notification_keywords, subject)
        if kw:
            return EmailCategory.NOTIFICATION, f"Benachrichtigungs-Signal im Betreff: '{kw}'"

        # 8. Age-based Archiving
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
            email.is_protected = self.is_protected_sender(email)
        return emails
