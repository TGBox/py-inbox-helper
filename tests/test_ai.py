"""Tests for Hybrid AI client (Ollama and Cloud API)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from py_inbox_helper.models import EmailItem, EmailCategory
from py_inbox_helper.ai import AiConfig, AiClient


def make_sample_email(subject: str, body: str) -> EmailItem:
    return EmailItem(
        id="item-ai-test",
        entry_id="EID-AI",
        store_id="store-1",
        account_name="user@test.de",
        subject=subject,
        sender_name="Partner",
        sender_email="partner@extern.de",
        received_time=datetime.now(timezone.utc),
        body_preview=body,
    )


@patch("requests.get")
def test_ai_client_availability_check(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    client = AiClient(AiConfig(provider="ollama", endpoint_url="http://localhost:11434"))
    assert client.is_available() is True
    mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=3)


@patch("requests.post")
def test_ai_client_ollama_summarization(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"response": "Der Absender bittet um Freigabe des Projektbudgets bis morgen."}
    )

    client = AiClient(AiConfig(provider="ollama", model_name="llama3.2"))
    email = make_sample_email("Budget Freigabe", "Hallo Daniel, bitte prüfe das Budget...")

    summary = client.summarize_email(email)
    assert "Projektbudgets" in summary
    assert mock_post.called


@patch("requests.post")
def test_ai_client_classification(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"response": "INVOICE_FINANCE: Rechnungskorrektur für Monat September"}
    )

    client = AiClient(AiConfig(provider="ollama"))
    email = make_sample_email("Korrekturbeleg 9/2026", "Sehr geehrte Damen und Herren...")

    cat, reason = client.classify_email(email)
    assert cat == EmailCategory.INVOICE_FINANCE
    assert "KI:" in reason or "Rechnungskorrektur" in reason


@patch("requests.post")
def test_ai_client_handles_offline_gracefully(mock_post):
    mock_post.side_effect = Exception("Connection refused")

    client = AiClient(AiConfig(provider="ollama"))
    email = make_sample_email("Unklarer Betreff", "Etwas Text")

    cat, reason = client.classify_email(email)
    assert cat is None
    assert "offline" in reason.lower() or "nicht erreichbar" in reason.lower()


def test_ai_config_persistence(tmp_path):
    cfg_file = tmp_path / "ai_config.json"
    cfg = AiConfig(provider="ollama", model_name="mistral", endpoint_url="http://localhost:11434")
    cfg.save_to_path(cfg_file)
    assert cfg_file.exists()

    loaded = AiConfig.load_from_path(cfg_file)
    assert loaded.provider == "ollama"
    assert loaded.model_name == "mistral"
    assert loaded.endpoint_url == "http://localhost:11434"


def test_ai_client_check_availability_disabled():
    client = AiClient(AiConfig(provider="disabled"))
    is_avail, msg = client.check_availability()
    assert is_avail is False
    assert "Deaktiviert" in msg


@patch("requests.get")
def test_ai_client_check_availability_ollama_no_models(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"models": []}
    )
    client = AiClient(AiConfig(provider="ollama", model_name="llama3.2"))
    is_avail, msg = client.check_availability()
    assert is_avail is False
    assert "Keine Modelle" in msg


@patch("requests.get")
def test_ai_client_check_availability_ollama_model_missing(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"models": [{"name": "qwen2.5:latest"}]}
    )
    client = AiClient(AiConfig(provider="ollama", model_name="llama3.2"))
    is_avail, msg = client.check_availability()
    assert is_avail is False
    assert "nicht in Ollama gefunden" in msg


@patch("requests.get")
def test_ai_client_check_availability_ollama_model_found(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"models": [{"name": "llama3.2:latest"}]}
    )
    client = AiClient(AiConfig(provider="ollama", model_name="llama3.2"))
    is_avail, msg = client.check_availability()
    assert is_avail is True
    assert "Bereit" in msg


@patch("requests.get")
def test_ai_client_check_availability_ollama_offline(mock_get):
    import requests
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
    client = AiClient(AiConfig(provider="ollama"))
    is_avail, msg = client.check_availability()
    assert is_avail is False
    assert "nicht erreichbar" in msg.lower()
