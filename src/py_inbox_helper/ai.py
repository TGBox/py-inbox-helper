"""Hybrid AI integration supporting local Ollama models and cloud APIs."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Optional, Tuple
import requests

from py_inbox_helper.models import EmailCategory, EmailItem

logger = logging.getLogger(__name__)


@dataclass
class AiConfig:
    """Configuration for AI provider (local Ollama or OpenAI-compatible cloud endpoint)."""
    provider: str = "ollama"  # "ollama", "openai_compatible", "disabled"
    endpoint_url: str = "http://localhost:11434"
    model_name: str = "llama3.2"
    api_key: Optional[str] = None
    timeout_seconds: int = 10


class AiClient:
    """Client for local Ollama and cloud LLMs for email summarization and categorization."""

    def __init__(self, config: Optional[AiConfig] = None):
        self.config = config or AiConfig()

    def is_available(self) -> bool:
        """Quickly tests if the AI endpoint is alive."""
        if self.config.provider == "disabled":
            return False

        try:
            if self.config.provider == "ollama":
                url = f"{self.config.endpoint_url.rstrip('/')}/api/tags"
                res = requests.get(url, timeout=3)
                return res.status_code == 200
            elif self.config.provider == "openai_compatible":
                url = f"{self.config.endpoint_url.rstrip('/')}/models"
                headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
                res = requests.get(url, headers=headers, timeout=3)
                return res.status_code in (200, 401)
        except Exception:
            return False
        return False

    def generate(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Sends a completion request to the configured AI provider."""
        if self.config.provider == "disabled":
            return None

        try:
            if self.config.provider == "ollama":
                url = f"{self.config.endpoint_url.rstrip('/')}/api/generate"
                payload = {
                    "model": self.config.model_name,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                }
                res = requests.post(url, json=payload, timeout=self.config.timeout_seconds)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("response", "").strip()

            elif self.config.provider == "openai_compatible":
                url = f"{self.config.endpoint_url.rstrip('/')}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                }
                if self.config.api_key:
                    headers["Authorization"] = f"Bearer {self.config.api_key}"

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": 0.2,
                }
                res = requests.post(url, json=payload, headers=headers, timeout=self.config.timeout_seconds)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()

        except Exception as ex:
            logger.warning("AI generation failed: %s", ex)
            return None

        return None

    def summarize_email(self, email: EmailItem) -> str:
        """Generates a concise 1-2 sentence German summary of an email."""
        system_prompt = (
            "Du bist ein intelligenter E-Mail-Assistent. Fasse die gegebene E-Mail in "
            "maximal 1-2 kurzen, prägnanten deutschen Sätzen zusammen. Konzentriere dich auf den Kern: "
            "Wer will was bis wann?"
        )
        prompt = (
            f"Betreff: {email.subject}\n"
            f"Absender: {email.sender_name} <{email.sender_email}>\n"
            f"Inhalt:\n{email.body_preview[:800]}\n"
        )
        resp = self.generate(prompt, system_prompt)
        if resp:
            return resp
        return "Keine Zusammenfassung verfügbar (KI offline oder nicht erreichbar)."

    def classify_email(self, email: EmailItem) -> Tuple[Optional[EmailCategory], str]:
        """Classifies an ambiguous email into standard categories."""
        system_prompt = (
            "Du bist ein E-Mail-Klassifikator. Antworte GENAU in diesem Format:\n"
            "<KATEGORIE>: <Kurze Begründung auf Deutsch>\n"
            "Erlaubte Kategorien:\n"
            "- NEWSLETTER (Werbung, Angebote, Produkt-Updates)\n"
            "- INVOICE_FINANCE (Rechnungen, Belege, Zahlungen, Buchhaltung)\n"
            "- NOTIFICATION (Automatisierte Systemberichte, No-Reply, Logins)\n"
            "- IMPORTANT_ACTION (Wichtige Mails mit Frist oder Handlungsbedarf)\n"
            "- RESUBMISSION (Wiedervorlage, Nachfassen, Erinnerungen)\n"
            "- JUNK (Spam, Phishing, Gewinnspiele)\n"
            "- UNCLASSIFIED (Sonstiges/Privat)\n"
        )
        prompt = (
            f"Betreff: {email.subject}\n"
            f"Absender: {email.sender_name} <{email.sender_email}>\n"
            f"Vorschau:\n{email.body_preview[:400]}\n"
        )
        resp = self.generate(prompt, system_prompt)
        if not resp:
            return None, "KI offline oder nicht erreichbar"

        # Parse category from response
        first_line = resp.splitlines()[0].strip()
        for cat in EmailCategory:
            if first_line.upper().startswith(cat.value):
                reason = first_line[len(cat.value):].lstrip(": -").strip()
                return cat, f"KI: {reason or 'Automatisch erkannt'}"

        return EmailCategory.UNCLASSIFIED, f"KI: {resp[:60]}"
