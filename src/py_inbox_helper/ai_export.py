"""Compact Markdown export of an analysis, prepared for review with an AI assistant."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from py_inbox_helper.models import EmailCategory, EmailItem, html_to_text

DEFAULT_BODY_LIMIT = 500
TOP_SENDER_COUNT = 15

CATEGORY_LABELS: dict[EmailCategory, str] = {
    EmailCategory.UNCLASSIFIED: "Nicht klassifiziert",
    EmailCategory.NEWSLETTER: "Newsletter & Promo",
    EmailCategory.INVOICE_FINANCE: "Rechnungen & Finanzen",
    EmailCategory.NOTIFICATION: "Benachrichtigungen",
    EmailCategory.IMPORTANT_ACTION: "Wichtig / Aktion",
    EmailCategory.RESUBMISSION: "Wiedervorlage",
    EmailCategory.ARCHIVE_OLD: "Archivierung (>180T)",
    EmailCategory.JUNK: "Junk / Papierkorb",
}

_WS_RE = re.compile(r"\s+")


def plain_text(email: EmailItem) -> str:
    """Returns the mail body as a single line of plain text (HTML stripped if needed)."""
    if email.body_text:
        return _WS_RE.sub(" ", email.body_text).strip()
    return html_to_text(email.body_html)


def _excerpt(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " […]"


def _fmt_date(dt: datetime) -> str:
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")


def _one_line(value: str) -> str:
    return _WS_RE.sub(" ", value or "").strip()


def build_ai_export(
    emails: list[EmailItem],
    account_name: str = "",
    notes: str = "",
    include_body: bool = True,
    body_limit: int = DEFAULT_BODY_LIMIT,
) -> str:
    """Builds a Markdown document with an overview block and one compact entry per mail."""
    lines: list[str] = ["# Postfach-Analyse (Export für KI-Auswertung)", ""]
    lines.append(f"- Postfach: {account_name or 'unbekannt'}")
    if notes:
        lines.append(f"- Analyse: {_one_line(notes)}")
    lines.append(f"- Exportiert am: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    lines.append(f"- Anzahl E-Mails: {len(emails)}")
    if emails:
        times = [e.received_time for e in emails]
        lines.append(f"- Zeitraum: {_fmt_date(min(times))} bis {_fmt_date(max(times))}")
    lines.append(f"- Mail-Text enthalten: {'ja, gekürzt auf ' + str(body_limit) + ' Zeichen' if include_body else 'nein'}")
    lines.append("")
    lines.append(
        "Die Kategorien und Begründungen stammen aus der automatischen, regelbasierten Analyse. "
        "VIP/geschützte Absender werden bei Aufräumaktionen nie verändert."
    )
    lines.append("")

    # Overview: categories
    lines += ["## Übersicht nach Kategorie", "", "| Kategorie | Anzahl | ungelesen |", "|---|---:|---:|"]
    by_cat = Counter(e.assigned_category for e in emails)
    unread_by_cat = Counter(e.assigned_category for e in emails if not e.is_read)
    for cat, label in CATEGORY_LABELS.items():
        if by_cat[cat]:
            lines.append(f"| {label} | {by_cat[cat]} | {unread_by_cat[cat]} |")
    protected = sum(1 for e in emails if e.is_protected)
    lines += ["", f"Geschützte Absender (VIP/Whitelist): {protected} E-Mails", ""]

    # Overview: top senders
    lines += ["## Top-Absender", "", "| Absender | Anzahl | häufigste Kategorie |", "|---|---:|---|"]
    by_sender: dict[str, list[EmailItem]] = {}
    for e in emails:
        by_sender.setdefault((e.sender_email or e.sender_name).lower(), []).append(e)
    top = sorted(by_sender.items(), key=lambda kv: len(kv[1]), reverse=True)[:TOP_SENDER_COUNT]
    for addr, items in top:
        main_cat = Counter(i.assigned_category for i in items).most_common(1)[0][0]
        lines.append(f"| {addr} | {len(items)} | {CATEGORY_LABELS[main_cat]} |")
    lines.append("")

    # Detail entries, newest first
    lines += ["## E-Mails", ""]
    for idx, e in enumerate(sorted(emails, key=lambda m: m.received_time, reverse=True), start=1):
        flags = ["ungelesen" if not e.is_read else "gelesen"]
        if e.is_protected:
            flags.append("geschützt")
        if e.has_unsubscribe_header:
            flags.append("Abmeldelink")
        lines.append(f"### {idx}. {_one_line(e.subject) or '(Kein Betreff)'}")
        lines.append(f"- Von: {_one_line(e.sender_name)} <{e.sender_email}>")
        lines.append(f"- Datum: {_fmt_date(e.received_time)} | Ordner: {e.folder_path} | {', '.join(flags)}")
        lines.append(f"- Kategorie: {CATEGORY_LABELS[e.assigned_category]} – {_one_line(e.classification_reason) or 'keine Begründung'}")
        if include_body:
            body = _excerpt(plain_text(e), body_limit)
            lines.append(f"- Text: {body or '(kein Text geladen)'}")
        lines.append("")

    return "\n".join(lines)


def export_for_ai(
    emails: list[EmailItem],
    target_path: Path,
    account_name: str = "",
    notes: str = "",
    include_body: bool = True,
    body_limit: int = DEFAULT_BODY_LIMIT,
) -> Path:
    """Writes the AI export as a UTF-8 Markdown file and returns its path."""
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        build_ai_export(emails, account_name, notes, include_body, body_limit), encoding="utf-8"
    )
    return target
