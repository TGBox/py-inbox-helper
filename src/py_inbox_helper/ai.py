"""Hybrid AI integration supporting local Ollama models and cloud APIs."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

from py_inbox_helper.models import EmailCategory, EmailItem

logger = logging.getLogger(__name__)


@dataclass
class AiConfig:
    """Configuration for AI provider (local Ollama or OpenAI-compatible cloud endpoint)."""
    provider: str = "disabled"  # "disabled", "ollama", "openai_compatible"
    endpoint_url: str = "http://localhost:11434"
    model_name: str = "llama3.2"
    api_key: Optional[str] = None
    timeout_seconds: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "endpoint_url": self.endpoint_url,
            "model_name": self.model_name,
            "api_key": self.api_key,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AiConfig:
        return cls(
            provider=data.get("provider", "disabled"),
            endpoint_url=data.get("endpoint_url", "http://localhost:11434"),
            model_name=data.get("model_name", "llama3.2"),
            api_key=data.get("api_key"),
            timeout_seconds=int(data.get("timeout_seconds", 10)),
        )

    def save_to_path(self, path: Optional[Path] = None) -> None:
        target = path or (Path.home() / ".py_inbox_helper" / "ai_config.json")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as ex:
            logger.warning("Could not save AI config: %s", ex)

    @classmethod
    def load_from_path(cls, path: Optional[Path] = None) -> AiConfig:
        target = path or (Path.home() / ".py_inbox_helper" / "ai_config.json")
        if not target.exists():
            return cls()
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as ex:
            logger.warning("Could not load AI config from %s: %s", target, ex)
            return cls()


class AiClient:
    """Client for local Ollama and cloud LLMs for email summarization and categorization."""

    def __init__(self, config: Optional[AiConfig] = None):
        self.config = config or AiConfig()

    def check_availability(self) -> Tuple[bool, str]:
        """Tests if the configured AI endpoint is alive and the model is available."""
        if self.config.provider == "disabled":
            return False, "Deaktiviert (Lokale Heuristik)"

        try:
            if self.config.provider == "ollama":
                url = f"{self.config.endpoint_url.rstrip('/')}/api/tags"
                res = requests.get(url, timeout=3)
                if res.status_code == 200:
                    try:
                        data = res.json()
                        if isinstance(data, dict) and "models" in data:
                            model_list = data.get("models", [])
                            if not model_list:
                                return False, "Keine Modelle in Ollama gefunden"
                            target = (self.config.model_name or "").strip().lower()
                            if target:
                                model_names = [
                                    m.get("name", "").lower()
                                    for m in model_list
                                    if isinstance(m, dict) and "name" in m
                                ]
                                matched = any(
                                    target == name or name.startswith(f"{target}:") or target in name
                                    for name in model_names
                                )
                                if not matched:
                                    return False, f"Modell '{self.config.model_name}' nicht in Ollama gefunden"
                    except Exception:
                        pass
                    return True, f"Bereit ({self.config.model_name})"
                return False, f"Ollama HTTP {res.status_code}"

            elif self.config.provider == "openai_compatible":
                url = f"{self.config.endpoint_url.rstrip('/')}/models"
                headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
                res = requests.get(url, headers=headers, timeout=3)
                if res.status_code in (200, 401):
                    return True, f"Bereit ({self.config.model_name})"
                return False, f"API HTTP {res.status_code}"

        except requests.exceptions.ConnectionError:
            return False, "Verbindung abgelehnt (Server nicht erreichbar)"
        except requests.exceptions.Timeout:
            return False, "Zeitüberschreitung (Timeout)"
        except Exception as ex:
            return False, f"Fehler: {ex}"

        return False, "Unbekannter Status"

    def is_available(self) -> bool:
        """Quickly tests if the AI endpoint is alive."""
        return self.check_availability()[0]

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
