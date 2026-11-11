"""Shared pytest fixtures."""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory, monkeypatch):
    """Redirects Path.home() so tests never touch the real ~/.py_inbox_helper
    (whitelist, backups, saved analyses, IMAP profiles)."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home
