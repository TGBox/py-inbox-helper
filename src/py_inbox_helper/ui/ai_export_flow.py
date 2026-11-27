"""Shared UI flow for the "Für KI exportieren" action."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from py_inbox_helper.ai_export import DEFAULT_BODY_LIMIT, export_for_ai
from py_inbox_helper.models import EmailItem


def run_ai_export(parent: QWidget, emails: list[EmailItem], account_name: str = "", notes: str = "") -> Path | None:
    """Asks whether mail text should be included, lets the user pick a file and writes the export."""
    if not emails:
        QMessageBox.information(parent, "Hinweis", "Es sind keine analysierten E-Mails zum Exportieren vorhanden.")
        return None

    box = QMessageBox(parent)
    box.setWindowTitle("Für KI exportieren")
    box.setIcon(QMessageBox.Question)
    box.setText("Sollen die Mail-Texte mit exportiert werden?")
    box.setInformativeText(
        f"Mit Text: zusätzlich die ersten {DEFAULT_BODY_LIMIT} Zeichen jeder Mail (ohne HTML).\n"
        "Ohne Text: nur Absender, Betreff, Datum, Kategorie und Begründung.\n\n"
        "Hinweis: Mail-Texte können personenbezogene oder vertrauliche Daten enthalten. "
        "Prüfe vor dem Hochladen zu einer externen KI, ob das erlaubt ist."
    )
    with_body = box.addButton("Mit Mail-Text", QMessageBox.AcceptRole)
    without_body = box.addButton("Nur Metadaten", QMessageBox.AcceptRole)
    box.addButton("Abbrechen", QMessageBox.RejectRole)
    box.setDefaultButton(without_body)
    box.exec()
    clicked = box.clickedButton()
    if clicked not in (with_body, without_body):
        return None

    default_name = f"postfach_analyse_ki_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    target, _ = QFileDialog.getSaveFileName(
        parent, "Für KI exportieren", default_name, "Markdown-Dateien (*.md);;Textdateien (*.txt)"
    )
    if not target:
        return None

    try:
        path = export_for_ai(
            emails, Path(target), account_name=account_name, notes=notes, include_body=clicked is with_body
        )
    except Exception as ex:
        QMessageBox.critical(parent, "Export fehlgeschlagen", f"Fehler beim Exportieren:\n{ex}")
        return None

    QMessageBox.information(
        parent,
        "Export erfolgreich",
        f"{len(emails)} E-Mails wurden exportiert nach:\n{path}\n\n"
        "Die Datei kann direkt in einen KI-Chat hochgeladen werden.",
    )
    return path
