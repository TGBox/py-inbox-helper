"""Abstract base interface for mail providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from py_inbox_helper.models import EmailItem, ExecutionResult, PlannedAction


@dataclass
class AccountInfo:
    """Information about an email account or mailbox store."""
    id: str
    name: str
    email_address: str
    is_default: bool = False
    store_type: str = "Exchange/Office365"


@dataclass
class FolderInfo:
    """Folder representation inside an account."""
    id: str
    name: str
    path: str
    item_count: int = 0
    unread_count: int = 0
    is_inbox: bool = False


class BaseMailProvider(ABC):
    """Abstract interface to allow supporting multiple providers (Outlook COM, Graph API, IMAP)."""

    @abstractmethod
    def list_accounts(self) -> List[AccountInfo]:
        """Lists all configured accounts / shared mailboxes."""
        pass

    @abstractmethod
    def list_folders(self, account_id: str) -> List[FolderInfo]:
        """Lists available mail folders for the given account."""
        pass

    @abstractmethod
    def fetch_emails(
        self,
        account_id: str,
        folder_paths: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        max_count: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[EmailItem]:
        """Fetches email items according to folder and date filters."""
        pass

    @abstractmethod
    def execute_action(self, action: PlannedAction, account_id: str) -> ExecutionResult:
        """Executes a single planned action."""
        pass

    @abstractmethod
    def restore_item(
        self,
        entry_id: str,
        store_id: str,
        target_folder: str,
        is_read: bool,
        categories: List[str],
    ) -> None:
        """Restores an item to its original folder and attributes during rollback."""
        pass
