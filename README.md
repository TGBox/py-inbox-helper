# py-inbox-helper

Eine moderne Python-Desktop-Anwendung (PySide6), um ein lange vernachlässigtes, chaotisches E-Mail-Postfach mit tausenden ungelesenen Nachrichten systematisch zu analysieren, aufzuräumen, Werbeabonnements abzubestellen, Aktionen feingranular zu planen und erst nach erfolgreichem Dry-Run und Freigabe sicher auszuführen.

---

## Hauptfunktionen

- **Microsoft 365 / Outlook Desktop Integration**:
  - Direkte MAPI-Anbindung an die lokale Microsoft Outlook Installation (`pywin32`) – keine umständliche Azure App Registration oder Administrator-Consent erforderlich.
  - Unterstützt mehrere eingerichtete Konten und geteilte Postfächer (Shared Mailboxes).
  - Anbieterunabhängige Architektur (`BaseMailProvider`), sodass künftig auch andere Protokolle (IMAP, Microsoft Graph REST API) nahtlos angebunden werden können.
  - Enthält einen integrierten **Demo-/Mock-Modus** zum risikolosen Testen ohne aktives Outlook.

- **Intelligente E-Mail-Analyse & Kategorisierung**:
  - Schnelle, regelbasierte Heuristik (List-Unsubscribe-Header, Betreffmuster, Absender, Alter, Priorität).
  - Erkennung von:
    - **Newsletter & Werbung** (inkl. Prüfung auf One-Click-Abmeldung nach RFC 8058/2369)
    - **Rechnungen & Finanzen** (automatische Zuordnung & Tagging)
    - **Benachrichtigungen** (No-Reply, Systemmeldungen)
    - **Wichtig / Handlungsbedarf** (Dringende Mails, Fristen, hohe Priorität)
    - **Wiedervorlage** (Erinnerungen, Nachfassen)
    - **Alte E-Mails / Archiv** (strukturierte Jahres-Unterordner wie `06_Archiv/2024`)
    - **Junk / Unerwünscht** (Verschieben in Gelöschte Elemente)
  - Modulares Design mit `BaseEmailClassifier`: Lokale KI-Modelle (z. B. Ollama / lokales LLM) können jederzeit als zusätzliches Klassifizierungs-Backend nachgerüstet werden.

- **Smarte Voreinstellungen & Feingranularer Regel-Editor**:
  - Konfigurierbare Zielordner (z. B. `01_Wiedervorlage`, `02_Wichtig`, `03_Rechnungen & Finanzen`, `04_Newsletter`, `05_Benachrichtigungen`, `06_Archiv/{Jahr}`).
  - Zielordner werden bei Bedarf automatisch in Outlook angelegt.
  - Individuelle Einstellung pro Kategorie: Als gelesen markieren, Jahresordner anlegen, Newsletter abmelden, Kategorien/Flags vergeben.

- **Dry-Run Simulation & Änderungsprotokoll**:
  - Führt vor jeder tatsächlichen Änderung eine vollständige Simulation durch.
  - Tabellarische Vorschau aller geplanten Aktionen mit Deaktivierungs-Option für einzelne Mails.
  - Export des Änderungsprotokolls als ansprechender **HTML-Bericht** und als **JSON-Datei**.
  - **Ausdrückliche Nutzer-Freigabe**: Änderungen werden erst nach Bestätigung angewendet.

- **Ausfallschutz & 1-Klick Rollback (Backup)**:
  - Vor der Ausführung wird automatisch ein vollständiger Wiederherstellungspunkt (`BackupSnapshot`) auf der Festplatte gespeichert.
  - **1-Klick Wiederherstellung**: Stellt alle Elemente im Fehlerfall vollständig in ihre Ursprungsordner und ihren vorherigen Gelesen-/Markierungs-Zustand zurück.
  - Sanftes Löschen: Löschaktionen verschieben Mails in den Outlook-Papierkorb, nichts wird permanent vernichtet.

- **Moderne Benutzeroberfläche (PySide6)**:
  - Dunkles, augenschonendes Theme mit klaren Status-Badges, KPI-Metriken und asynchronen Hintergrund-Threads (`QThread`), sodass die Oberfläche niemals einfriert.
  - **Vollbild- & Fenstermodus**: Umschaltbar per Tastenkombination `F11` (oder Escape zum Beenden) sowie über die Schaltfläche in der Kopfzeile.

---

## Installation & Schnellstart

Das Projekt wird mit [`uv`](https://github.com/astral-sh/uv) verwaltet.

### 1. Abhängigkeiten installieren

```bash
uv sync
```

### 2. Anwendung starten

```bash
uv run py-inbox-helper
```

---

## Tests ausführen

Die gesamte Geschäftslogik, Heuristik, Unsubscribe-Extraktion, Snapshot-Wiederherstellung und GUI-Integration ist mit pytest abgedeckt:

```bash
uv run pytest
```

---

## Projektstruktur

```text
src/py_inbox_helper/
├── __init__.py           # Einstiegspunkt (main)
├── models.py             # Datenmodelle (EmailItem, PlannedAction, ActionPlan, BackupSnapshot)
├── analyzer.py           # Regelbasierter E-Mail-Klassifizierer & BaseEmailClassifier
├── planner.py            # Aktionsplanung & Dry-Run-Simulation
├── protocol.py           # Erstellung & Export von Änderungsprotokollen (HTML, JSON)
├── unsubscribe.py        # RFC 8058 / 2369 Newsletter-Abmelde-Engine
├── backup.py             # Snapshot-Sicherung & 1-Klick-Rollback
├── provider/
│   ├── base.py           # BaseMailProvider Abstraktion
│   ├── mock_provider.py  # In-Memory Demo-Postfach für Tests
│   └── outlook_provider.py # Windows COM/MAPI Microsoft Outlook Desktop Client
└── ui/
    ├── styles.py         # Modernes Dark Theme (QSS)
    ├── workers.py        # Asynchrone QThread-Worker (ScanWorker, ExecutionWorker, RestoreWorker)
    ├── main_window.py    # Hauptfenster mit F11-Vollbildmodus & Navigation
    └── tabs/
        ├── scan_tab.py       # Postfach- & Ordnerauswahl, Filter
        ├── analysis_tab.py   # KPI-Karten, E-Mail-Tabelle & Detailansicht
        ├── rules_tab.py      # Ordner-Presets & Regel-Editor
        ├── protocol_tab.py   # Dry-Run Simulation, Freigabe & Export
        └── backup_tab.py     # Live-Ausführung, Backups & Rollback
```
