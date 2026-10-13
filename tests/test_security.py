"""Tests for security module and credential vault migration."""
import json
from pathlib import Path
from unittest.mock import patch

from py_inbox_helper.ai import AiConfig
from py_inbox_helper.provider.imap_provider import ImapConfig, ImapProfileManager
from py_inbox_helper.security import delete_secret, get_secret, store_secret


def test_secret_storage_roundtrip():
    test_key = "test_cred_key_123"
    test_val = "secret_password_xyz!"

    assert store_secret(test_key, test_val) is True
    assert get_secret(test_key) == test_val
    assert delete_secret(test_key) is True


def test_imap_profile_legacy_migration_and_scrub(tmp_path: Path):
    cfg_file = tmp_path / "imap_profiles.json"
    # Write a legacy profile with plaintext password
    legacy_data = [
        {
            "profile_id": "legacy-prof-1",
            "account_name": "Altes Postfach",
            "host": "imap.legacy.com",
            "port": 993,
            "use_ssl": True,
            "username": "user@legacy.com",
            "password": "unencrypted_secret_123",
        }
    ]
    cfg_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    manager = ImapProfileManager(config_path=cfg_file)
    profiles = manager.list_profiles()

    assert len(profiles) == 1
    assert profiles[0].password == "unencrypted_secret_123"

    # Verify JSON file on disk was scrubbed of plaintext password
    disk_data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert disk_data[0]["password"] == ""

    # Clean up keyring
    delete_secret("imap_legacy-prof-1")


def test_ai_config_legacy_migration_and_scrub(tmp_path: Path):
    cfg_file = tmp_path / "ai_config.json"
    # Write a legacy config with plaintext API key
    legacy_data = {
        "provider": "openai",
        "endpoint_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
        "api_key": "sk-legacy-plaintext-key-12345",
        "timeout_seconds": 15,
    }
    cfg_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    loaded = AiConfig.load_from_path(cfg_file)
    assert loaded.api_key == "sk-legacy-plaintext-key-12345"

    # Verify JSON file on disk was scrubbed
    disk_data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert disk_data.get("api_key") is None

    # Clean up keyring
    delete_secret("ai_api_key")
