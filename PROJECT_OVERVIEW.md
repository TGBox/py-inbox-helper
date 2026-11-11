# Projekt-Architektur-Report: `py-inbox-helper`

## 1. Kennzahlen & Token-Budget

- **Analysierte Dateien**: 56
- **Gesamte Codezeilen (LOC)**: 9,624
- **Gesamter Token-Bedarf**: 98,477 Tokens
- **Geschätzte Input-Kosten (Claude 3.5 Sonnet)**: ~$0.2954

## 2. Top-Token-Verbraucher (Größte Dateien)

| Datei | Zeilen | Tokens | % vom Gesamtprojekt |
| --- | --- | --- | --- |
| `src/py_inbox_helper/ui/tabs/analysis_tab.py` | 823 | 9,775 | 9.9% |
| `src/py_inbox_helper/ui/main_window.py` | 645 | 7,540 | 7.7% |
| `src/py_inbox_helper/ui/email_preview_dialog.py` | 575 | 6,132 | 6.2% |
| `src/py_inbox_helper/provider/mock_provider.py` | 399 | 4,860 | 4.9% |
| `src/py_inbox_helper/ui/saved_analyses_dialog.py` | 402 | 4,279 | 4.3% |
| `src/py_inbox_helper/ui/tabs/scan_tab.py` | 371 | 4,064 | 4.1% |
| `src/py_inbox_helper/provider/imap_provider.py` | 389 | 3,981 | 4.0% |
| `src/py_inbox_helper/provider/outlook_provider.py` | 381 | 3,978 | 4.0% |
| `PROJECT_OVERVIEW.md` | 398 | 3,710 | 3.8% |
| `tests/test_ui.py` | 341 | 3,605 | 3.7% |

## 3. Erkannte Abhängigkeiten & Module

- `py_inbox_helper` (107x importiert)
- `PySide6` (28x importiert)
- `datetime` (26x importiert)
- `__future__` (25x importiert)
- `typing` (24x importiert)
- `pathlib` (14x importiert)
- `pytest` (13x importiert)
- `json` (8x importiert)
- `dataclasses` (8x importiert)
- `unittest` (5x importiert)
- `logging` (5x importiert)
- `uuid` (4x importiert)
- `os` (3x importiert)
- `re` (3x importiert)
- `email` (3x importiert)

## 4. Bereinigter Dateibaum (.gitignore berücksichtigt)

```text
- .agents/rules/fastapi_best_practices.md
- .agents/rules/general_guidelines.md
- .agents/rules/pyside6_gui_conventions.md
- .agents/rules/python_standards.md
- .agents/skills/code-review/SKILL.md
- .agents/skills/test-runner/SKILL.md
- .gitignore
- .python-version
- AGENTS.md
- CHANGELOG.md
- PROJECT_OVERVIEW.md
- README.md
- pyproject.toml
- src/py_inbox_helper/__init__.py
- src/py_inbox_helper/ai.py
- src/py_inbox_helper/analysis_storage.py
- src/py_inbox_helper/analyzer.py
- src/py_inbox_helper/backup.py
- src/py_inbox_helper/models.py
- src/py_inbox_helper/planner.py
- src/py_inbox_helper/protocol.py
- src/py_inbox_helper/provider/__init__.py
- src/py_inbox_helper/provider/base.py
- src/py_inbox_helper/provider/imap_provider.py
- src/py_inbox_helper/provider/mock_provider.py
- src/py_inbox_helper/provider/outlook_provider.py
- src/py_inbox_helper/security.py
- src/py_inbox_helper/storage.py
- src/py_inbox_helper/ui/__init__.py
- src/py_inbox_helper/ui/email_preview_dialog.py
- src/py_inbox_helper/ui/main_window.py
- src/py_inbox_helper/ui/saved_analyses_dialog.py
- src/py_inbox_helper/ui/settings_dialog.py
- src/py_inbox_helper/ui/styles.py
- src/py_inbox_helper/ui/tabs/__init__.py
- src/py_inbox_helper/ui/tabs/analysis_tab.py
- src/py_inbox_helper/ui/tabs/backup_tab.py
- src/py_inbox_helper/ui/tabs/protocol_tab.py
- src/py_inbox_helper/ui/tabs/rules_tab.py
- src/py_inbox_helper/ui/tabs/scan_tab.py
- ... und 16 weitere Dateien
```

## 5. API-Skelette zentraler Python-Komponenten (ohne Rümpfe)

### `tests/test_ai.py`

```python
"""Tests for Hybrid AI client (Ollama and Cloud API)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from py_inbox_helper.models import EmailItem, EmailCategory
from py_inbox_helper.ai import AiConfig, AiClient

def make_sample_email(subject: str, body: str) -> EmailItem:
    ...

@patch('requests.get')
def test_ai_client_availability_check(mock_get):
    ...

@patch('requests.post')
def test_ai_client_ollama_summarization(mock_post):
    ...

@patch('requests.post')
def test_ai_client_classification(mock_post):
    ...

@patch('requests.post')
def test_ai_client_handles_offline_gracefully(mock_post):
    ...

def test_ai_config_persistence(tmp_path):
    ...

def test_ai_client_check_availability_disabled():
    ...

@patch('requests.get')
def test_ai_client_check_availability_ollama_no_models(mock_get):
    ...

@patch('requests.get')
def test_ai_client_check_availability_ollama_model_missing(mock_get):
    ...

@patch('requests.get')
def test_ai_client_check_availability_ollama_model_found(mock_get):
    ...

@patch('requests.get')
def test_ai_client_check_availability_ollama_offline(mock_get):
    ...
```

### `tests/test_analysis_storage.py`

```python
"""Tests for AnalysisStorageManager, AnalysisSession, and SavedAnalysesDialog."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from py_inbox_helper.analysis_storage import AnalysisStorageManager
from py_inbox_helper.models import AnalysisSession, EmailCategory, EmailItem
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.ui.main_window import MainWindow
from py_inbox_helper.ui.saved_analyses_dialog import SavedAnalysesDialog

@pytest.fixture(scope='session')
def qapp():
    ...

def _create_sample_email(email_id: str, subject: str='Test Mail') -> EmailItem:
    ...

def test_analysis_storage_manager_save_and_load(tmp_path: Path):
    ...

def test_analysis_storage_manager_list_and_delete(tmp_path: Path):
    ...

def test_analysis_storage_export_and_import(tmp_path: Path):
    ...

def test_saved_analyses_dialog(qapp, tmp_path: Path):
    ...

def test_main_window_save_and_load_workflow(qapp, tmp_path: Path):
    ...
```

### `tests/test_analyzer.py`

```python
"""Tests for email classification and heuristic rule analyzer."""
from datetime import datetime, timedelta, timezone
import pytest
from py_inbox_helper.models import EmailItem, EmailCategory
from py_inbox_helper.analyzer import EmailAnalyzer, RuleConfig

def make_email(subject: str, sender_name: str='Test Sender', sender_email: str='sender@example.com', body: str='', days_ago: int=10, headers: dict=None, importance: str='normal') -> EmailItem:
    ...

def test_classify_newsletter_by_header():
    ...

def test_classify_newsletter_by_keywords():
    ...

def test_classify_invoice_finance():
    ...

def test_classify_notification():
    ...

def test_classify_important_action():
    ...

def test_classify_archive_old():
    ...

def test_classify_vip_whitelist_sender():
    ...

def test_classify_offset_naive_datetime_does_not_fail():
    """Verify that an offset-naive datetime (e.g. from Outlook COM) doesn't raise TypeError."""
    ...
```

### `tests/test_backup.py`

```python
"""Tests for BackupManager and rollback snapshot persistence."""
from datetime import datetime, timezone
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from py_inbox_helper.models import EmailItem, BackupSnapshot
from py_inbox_helper.backup import BackupManager

def test_create_and_save_snapshot(tmp_path: Path):
    ...

def test_rollback_restoration(tmp_path: Path):
    ...

def test_granular_single_item_rollback(tmp_path: Path):
    ...
```

### `tests/test_email_preview.py`

```python
"""Tests for EmailPreviewDialog and integration with AnalysisTab."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from datetime import datetime, timezone
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from py_inbox_helper.models import EmailCategory, EmailItem
from py_inbox_helper.provider.mock_provider import MockMailProvider
from py_inbox_helper.ui.email_preview_dialog import EmailPreviewDialog
from py_inbox_helper.ui.main_window import MainWindow

@pytest.fixture(scope='session')
def qapp():
    ...

def test_preview_dialog_initialization(qapp):
    ...

def test_preview_dialog_navigation(qapp):
    ...

def test_preview_dialog_fullscreen_toggle(qapp):
    ...

def test_preview_dialog_headers_filter_and_copy(qapp):
    ...

def test_analysis_tab_opens_preview_window(qapp, tmp_path: Path):
    ...
```
