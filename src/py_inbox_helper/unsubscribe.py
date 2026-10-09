"""Unsubscribe mechanism for newsletters and promotional emails."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import requests

from py_inbox_helper.models import EmailItem


@dataclass
class UnsubscribeInfo:
    """Details parsed from email headers for unsubscribing."""
    has_unsubscribe: bool
    is_one_click: bool
    http_url: Optional[str] = None
    mailto_uri: Optional[str] = None


@dataclass
class UnsubscribeResult:
    """Outcome of attempting an unsubscription."""
    success: bool
    message: str
    target: str = ""


class UnsubscribeManager:
    """Handles parsing and executing unsubscriptions according to RFC 2369 / RFC 8058."""

    USER_AGENT = "PyInboxHelper/0.1.6"

    def inspect_email(self, email: EmailItem) -> UnsubscribeInfo:
        """Inspects an email item for unsubscribe options."""
        return UnsubscribeInfo(
            has_unsubscribe=email.has_unsubscribe_header,
            is_one_click=email.is_one_click_unsubscribe,
            http_url=email.unsubscribe_url,
            mailto_uri=email.unsubscribe_mailto,
        )

    def execute_unsubscribe(self, email: EmailItem) -> UnsubscribeResult:
        """Executes an unsubscription for the given email item."""
        info = self.inspect_email(email)

        if not info.has_unsubscribe:
            return UnsubscribeResult(
                success=False,
                message="Keine Abmelde-Header in der E-Mail gefunden.",
            )

        # 1. RFC 8058 One-Click HTTP POST
        if info.is_one_click and info.http_url:
            try:
                response = requests.post(
                    info.http_url,
                    data={"List-Unsubscribe": "One-Click"},
                    timeout=10,
                    headers={"User-Agent": self.USER_AGENT},
                )
                if response.status_code in (200, 202, 204):
                    return UnsubscribeResult(
                        success=True,
                        message=f"Erfolgreich abgemeldet via One-Click POST (Status {response.status_code})",
                        target=info.http_url,
                    )
                else:
                    return UnsubscribeResult(
                        success=False,
                        message=f"One-Click POST fehlgeschlagen (HTTP Status {response.status_code})",
                        target=info.http_url,
                    )
            except Exception as ex:
                return UnsubscribeResult(
                    success=False,
                    message=f"Fehler bei One-Click HTTP-Anfrage: {str(ex)}",
                    target=info.http_url,
                )

        # 2. Standard Mailto URI (can be executed via mail provider or MAPI)
        if info.mailto_uri:
            return UnsubscribeResult(
                success=True,
                message="Abmelde-E-Mail (mailto) vorbereitet.",
                target=info.mailto_uri,
            )

        # 3. Standard HTTP Web Link (requires manual user interaction in browser)
        if info.http_url:
            return UnsubscribeResult(
                success=True,
                message="Web-Abmeldelink gefunden (im Browser öffnen).",
                target=info.http_url,
            )

        return UnsubscribeResult(
            success=False,
            message="Kein gültiger Abmeldepfad extrahierbar.",
        )
