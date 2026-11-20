"""Shared pytest fixtures."""
from pathlib import Path

import keyring
import keyring.errors
from keyring.backend import KeyringBackend
import pytest


class _MemoryKeyring(KeyringBackend):
    """Keyring that lives only in memory, so tests never touch the OS credential store."""
    priority = 1

    def __init__(self):
        super().__init__()
        self._store = {}

    def get_password(self, service, username):
        return self._store.get((service, username))

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self._store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self._store[(service, username)]


@pytest.fixture(autouse=True)
def isolated_keyring():
    """Gives every test a fresh in-memory keyring instead of the real one."""
    previous = keyring.get_keyring()
    keyring.set_keyring(_MemoryKeyring())
    yield
    keyring.set_keyring(previous)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory, monkeypatch):
    """Redirects Path.home() so tests never touch the real ~/.py_inbox_helper
    (whitelist, backups, saved analyses, IMAP profiles)."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home
