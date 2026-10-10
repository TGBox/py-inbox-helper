---
name: test-runner
description: Führt die Test-Suite des Projekts aus und unterstützt bei der Analyse und Behebung von Fehlern.
---

# Test-Runner Skill

## Ablauf

1. **Passendes Testwerkzeug erkennen**:
   - Python: `uv run pytest`
   - Rust: `cargo test`
   - Node: `npm test` oder `npx vitest run`
2. **Tests ausführen**:
   - Führe die Tests im Root-Verzeichnis aus.
3. **Fehleranalyse**:
   - Bei fehlschlagenden Tests Stacktrace lokalisieren und Ursache im Code isolieren.
