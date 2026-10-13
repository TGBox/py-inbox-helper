"""Secure credential storage using OS keyring with graceful fallback."""
from __future__ import annotations

import logging
from typing import Optional
import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "py-inbox-helper"


def store_secret(key: str, value: str) -> bool:
    """Stores a secret securely in the OS keyring."""
    try:
        keyring.set_password(SERVICE_NAME, key, value)
        return True
    except Exception as ex:
        logger.warning("Could not store secret in keyring for %s: %s", key, ex)
        return False


def get_secret(key: str) -> Optional[str]:
    """Retrieves a secret from the OS keyring."""
    try:
        return keyring.get_password(SERVICE_NAME, key)
    except Exception as ex:
        logger.warning("Could not retrieve secret from keyring for %s: %s", key, ex)
        return None


def delete_secret(key: str) -> bool:
    """Deletes a secret from the OS keyring."""
    try:
        keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception as ex:
        logger.debug("Secret delete ignored or not found for %s: %s", key, ex)
        return False
