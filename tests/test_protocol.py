"""Tests for Change Protocol and export reports."""
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest

from py_inbox_helper.models import PlannedAction, ActionType, ExecutionResult
from py_inbox_helper.protocol import ProtocolGenerator


def test_protocol_generation_and_exports(tmp_path: Path):
    generator = ProtocolGenerator()
    results = [
        ExecutionResult(
            action=PlannedAction(
                email_id="item-1",
                email_subject="Wochenangebote",
                action_type=ActionType.MOVE_AND_MARK_READ,
                target_folder="04_Newsletter",
                mark_as_read=True,
                unsubscribe=True,
                unsubscribe_url="https://unsub.com/1",
            ),
            success=True,
            is_dry_run=True,
            message="Simuliert: Verschieben nach '04_Newsletter', Als gelesen markieren, Newsletter abmelden",
        ),
        ExecutionResult(
            action=PlannedAction(
                email_id="item-2",
                email_subject="Rechnung 2026",
                action_type=ActionType.MOVE,
                target_folder="03_Rechnungen & Finanzen",
                add_category="Finanzen",
            ),
            success=True,
            is_dry_run=True,
            message="Simuliert: Verschieben nach '03_Rechnungen & Finanzen', Kategorie 'Finanzen' setzen",
        ),
    ]

    summary = generator.build_summary("test@domain.com", results, is_dry_run=True)
    assert summary["total"] == 2
    assert summary["moved"] == 2
    assert summary["marked_read"] == 1
    assert summary["unsubscribed"] == 1

    # Test JSON export
    json_path = tmp_path / "protocol.json"
    generator.export_json(summary, results, json_path)
    assert json_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["summary"]["total"] == 2

    # Test HTML export
    html_path = tmp_path / "protocol.html"
    generator.export_html(summary, results, html_path)
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert "Änderungsprotokoll" in content
    assert "Wochenangebote" in content
    assert "Rechnung 2026" in content
