# py-inbox-helper

Eine moderne Python-Desktop-Anwendung (PySide6), um ein lange vernachlässigtes, chaotisches E-Mail-Postfach mit tausenden ungelesenen Nachrichten systematisch zu analysieren, aufzuräumen, Werbeabonnements abzubestellen, Aktionen feingranular zu planen und erst nach erfolgreichem Dry-Run und Freigabe sicher auszuführen.

---

## Hauptfunktionen

- **Microsoft 365 / Outlook Desktop & Generischer IMAP-Support**:
  - Direkte MAPI-Anbindung an die lokale Microsoft Outlook Installation (`pywin32`) – keine umständliche Azure App Registration oder Administrator-Consent erforderlich.
  - **Generischer IMAP-Provider (`ImapMailProvider`)**: Unterstützt Gmail, GMX, Web.de und eigene Mailserver mit lokaler Profilverwaltung.
  - Unterstützt mehrere eingerichtete Konten und geteilte Postfächer (Shared Mailboxes).
  - Integrierter **Demo-/Mock-Modus** zum risikolosen Testen ohne aktives Postfach.

- **Intelligente E-Mail-Analyse & VIP-Whitelist-Schutz**:
  - Schnelle, regelbasierte Heuristik (List-Unsubscribe-Header, Betreffmuster, Absender, Alter, Priorität).
  - **VIP- & Whitelist-Schutz**: Geschützte Absender/Domains (z. B. Familie, Vorgesetzte, Kunden) werden automatisch vor Löschung oder Archivierung geschützt.
  - Erkennung von:
    - **Newsletter & Werbung** (inkl. Prüfung auf One-Click-Abmeldung nach RFC 8058/2369)
    - **Rechnungen & Finanzen** (automatische Zuordnung & Tagging)
    - **Benachrichtigungen** (No-Reply, Systemmeldungen)
    - **Wichtig / Handlungsbedarf** (Dringende Mails, Fristen, hohe Priorität)
    - **Wiedervorlage** (Erinnerungen, Nachfassen)
    - **Alte E-Mails / Archiv** (strukturierte Jahres-Unterordner wie `06_Archiv/2024`)
    - **Junk / Unerwünscht** (Verschieben in Gelöschte Elemente)

- **Top-Absender-Clustering & Speicherplatz-Finder**:
  - Gruppierung aller E-Mails nach Absender mit Anzeige von Gesamtzahl, ungelesenen Mails und verbrauchtem Speicherplatz in MB.
  - Größenfilter für E-Mails (`> 1 MB`, `> 5 MB`, `> 10 MB`, `> 25 MB`), um gezielt Speicherfresser aufzuspüren.
  - 1-Klick-Aktionen zur Filterung und Absender-Whitelist-Aufnahme.

- **Hybrid-KI-Integration (Ollama / Cloud-Modelle)**:
  - Verbindung zu lokalem Ollama (`http://localhost:11434`, z. B. `llama3.2`, `mistral`) oder OpenAI-kompatiblen Cloud-Endpunkten.
  - 1-Klick-Zusammenfassungen im Vorschau-Panel (Kernbotschaft in 1–2 Sätzen).
  - Automatischer Fallback auf Heuristik, falls kein KI-Modell aktiv ist.

- **Smarte Voreinstellungen & Feingranularer Regel-Editor**:
  - Konfigurierbare Zielordner (z. B. `01_Wiedervorlage`, `02_Wichtig`, `03_Rechnungen & Finanzen`, `04_Newsletter`, `05_Benachrichtigungen`, `06_Archiv/{Jahr}`).
  - Zielordner werden bei Bedarf automatisch im Postfach angelegt.
  - Individuelle Einstellung pro Kategorie: Als gelesen markieren, Jahresordner anlegen, Newsletter abmelden, Kategorien/Flags vergeben.

- **Dry-Run Simulation & Änderungsprotokoll**:
  - Führt vor jeder tatsächlichen Änderung eine vollständige Simulation durch.
  - Tabellarische Vorschau aller geplanten Aktionen mit Deaktivierungs-Option für einzelne Mails.
  - Export des Änderungsprotokolls als ansprechender **HTML-Bericht** und als **JSON-Datei**.
  - **Ausdrückliche Nutzer-Freigabe**: Änderungen werden erst nach Bestätigung angewendet.

- **Ausfallschutz & Granulares Rollback (Backup)**:
  - Vor der Ausführung wird automatisch ein vollständiger Wiederherstellungspunkt (`BackupSnapshot`) auf der Festplatte gespeichert.
  - **Granulares Rollback**: Neben dem vollständigen Rollback können gezielt einzelne E-Mails aus einem Snapshot wiederhergestellt werden.
  - Sanftes Löschen: Löschaktionen verschieben Mails in den Papierkorb, nichts wird permanent vernichtet.

- **Moderne Benutzeroberfläche (PySide6)**:
  - Dunkles, augenschonendes Theme mit klaren Status-Badges, KPI-Metriken und asynchronen Hintergrund-Threads (`QThread`).
  - **Mehrfachauswahl & Kontextmenüs**: Zeilen per Shift/Strg markierbar mit Rechtsklick-Aktionen.
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

Die gesamte Logik, Heuristik, KI-Anbindung, IMAP-Provider, Speicher-Analyse, Snapshot-Wiederherstellung und GUI-Integration ist mit pytest abgedeckt:

```bash
uv run pytest
```

---

## Projektstruktur

```text
src/py_inbox_helper/
├── __init__.py           # Einstiegspunkt (main)
├── models.py             # Datenmodelle (EmailItem, PlannedAction, ActionPlan, BackupSnapshot)
├── analyzer.py           # Regelbasierter E-Mail-Klassifizierer mit VIP-Whitelist
├── ai.py                 # Hybrid-KI-Client (Ollama & Cloud REST API)
├── storage.py            # Speicher-Analyzer & SenderCluster
├── planner.py            # Aktionsplanung & Dry-Run-Simulation
├── protocol.py           # Erstellung & Export von Änderungsprotokollen (HTML, JSON)
├── unsubscribe.py        # RFC 8058 / 2369 Newsletter-Abmelde-Engine
├── backup.py             # Snapshot-Sicherung & 1-Klick- und Granulares Rollback
├── provider/
│   ├── base.py           # BaseMailProvider Abstraktion
│   ├── mock_provider.py  # In-Memory Demo-Postfach für Tests
│   ├── outlook_provider.py # Windows COM/MAPI Microsoft Outlook Desktop Client
│   └── imap_provider.py  # Generischer IMAP-Provider (Gmail, GMX, Web.de, Custom)
└── ui/
    ├── styles.py         # Modernes Dark Theme (QSS)
    ├── workers.py        # Asynchrone QThread-Worker (ScanWorker, ExecutionWorker, RestoreWorker)
    ├── settings_dialog.py # Dialog für KI-, IMAP- und VIP-Einstellungen
    ├── main_window.py    # Hauptfenster mit F11-Vollbildmodus & Navigation
    └── tabs/
        ├── scan_tab.py       # Postfach- & Ordnerauswahl, Filter
        ├── analysis_tab.py   # KPI-Karten, E-Mail-Tabelle, Top-Absender & KI-Vorschau
        ├── rules_tab.py      # Ordner-Presets & Regel-Editor
        ├── protocol_tab.py   # Dry-Run Simulation, Freigabe & Export
        └── backup_tab.py     # Live-Ausführung, Backups & Granulares Rollback
```
