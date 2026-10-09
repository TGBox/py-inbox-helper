"""Change protocol and audit log generator with HTML and JSON exports."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from py_inbox_helper.models import ExecutionResult


class ProtocolGenerator:
    """Generates structured summaries and export files for cleanup runs."""

    def build_summary(
        self,
        account_name: str,
        results: List[ExecutionResult],
        is_dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Calculates key operational statistics from execution or dry-run results."""
        total = len(results)
        success_count = sum(1 for r in results if r.success)
        moved = sum(1 for r in results if r.action.target_folder)
        marked_read = sum(1 for r in results if r.action.mark_as_read)
        marked_unread = sum(1 for r in results if r.action.mark_as_unread)
        unsubscribed = sum(1 for r in results if r.action.unsubscribe)
        flagged = sum(1 for r in results if r.action.set_flag or r.action.add_category)

        return {
            "account_name": account_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_dry_run": is_dry_run,
            "mode_label": "Dry-Run Simulation (Keine Änderungen geschrieben)" if is_dry_run else "Echte Ausführung",
            "total": total,
            "success_count": success_count,
            "failed_count": total - success_count,
            "moved": moved,
            "marked_read": marked_read,
            "marked_unread": marked_unread,
            "unsubscribed": unsubscribed,
            "flagged": flagged,
        }

    def export_json(
        self,
        summary: Dict[str, Any],
        results: List[ExecutionResult],
        output_path: Path,
    ) -> None:
        """Exports audit data to a JSON file."""
        data = {
            "summary": summary,
            "items": [
                {
                    "email_id": r.action.email_id,
                    "subject": r.action.email_subject,
                    "target_folder": r.action.target_folder,
                    "mark_as_read": r.action.mark_as_read,
                    "unsubscribe": r.action.unsubscribe,
                    "unsubscribe_url": r.action.unsubscribe_url,
                    "success": r.success,
                    "message": r.message,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in results
            ],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def export_html(
        self,
        summary: Dict[str, Any],
        results: List[ExecutionResult],
        output_path: Path,
    ) -> None:
        """Exports an aesthetically formatted HTML change protocol."""
        rows = []
        for r in results:
            badge_class = "badge-success" if r.success else "badge-danger"
            badge_text = "Erfolg" if r.success else "Fehler"
            rows.append(
                f"""<tr>
                    <td><strong>{r.action.email_subject}</strong><br><small style="color: #64748b;">ID: {r.action.email_id}</small></td>
                    <td>{r.action.target_folder or '<em>Kein</em>'}</td>
                    <td>{'Ja' if r.action.mark_as_read else 'Nein'}</td>
                    <td>{'Ja' if r.action.unsubscribe else 'Nein'}</td>
                    <td><span class="badge {badge_class}">{badge_text}</span></td>
                    <td>{r.message}</td>
                </tr>"""
            )

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Änderungsprotokoll - py-inbox-helper</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 32px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #1e293b;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
            border: 1px solid #334155;
        }}
        h1 {{
            margin-top: 0;
            color: #38bdf8;
            font-size: 28px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 14px;
            font-weight: 600;
            background-color: {'#0369a1' if summary['is_dry_run'] else '#15803d'};
            color: #ffffff;
            margin-bottom: 24px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .card {{
            background: #0f172a;
            border: 1px solid #334155;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .card .num {{
            font-size: 32px;
            font-weight: 700;
            color: #38bdf8;
            margin-bottom: 4px;
        }}
        .card .label {{
            font-size: 13px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px 14px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background: #0f172a;
            color: #94a3b8;
            font-weight: 600;
        }}
        tr:hover {{
            background: rgba(56, 189, 248, 0.05);
        }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-success {{ background: #166534; color: #bbf7d0; }}
        .badge-danger {{ background: #991b1b; color: #fecaca; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>E-Mail Änderungsprotokoll</h1>
        <div class="status-badge">{summary['mode_label']}</div>
        <p style="color: #94a3b8;">Konto: <strong>{summary['account_name']}</strong> | Erstellt am: {summary['timestamp']}</p>

        <div class="grid">
            <div class="card">
                <div class="num">{summary['total']}</div>
                <div class="label">Gesamt Aktionen</div>
            </div>
            <div class="card">
                <div class="num">{summary['moved']}</div>
                <div class="label">Verschoben</div>
            </div>
            <div class="card">
                <div class="num">{summary['marked_read']}</div>
                <div class="label">Als gelesen</div>
            </div>
            <div class="card">
                <div class="num">{summary['unsubscribed']}</div>
                <div class="label">Abgemeldet</div>
            </div>
        </div>

        <h2>Details der Aktionen</h2>
        <table>
            <thead>
                <tr>
                    <th>Betreff</th>
                    <th>Zielordner</th>
                    <th>Als gelesen</th>
                    <th>Abmelden</th>
                    <th>Status</th>
                    <th>Meldung / Ergebnis</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
