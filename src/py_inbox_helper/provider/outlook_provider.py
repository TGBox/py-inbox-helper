"""Outlook Desktop Client provider using Windows COM / MAPI."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
import pythoncom
import win32com.client

from py_inbox_helper.models import EmailItem, ExecutionResult, PlannedAction, ensure_utc
from py_inbox_helper.provider.base import AccountInfo, BaseMailProvider, FolderInfo

logger = logging.getLogger(__name__)

# MAPI Property Tag for Transport Message Headers (Internet Headers)
PR_TRANSPORT_MESSAGE_HEADERS = "http://schemas.microsoft.com/mapi/proptag/0x007D001E"

# Outlook Default Folder Enumerations
OL_FOLDER_INBOX = 6
OL_FOLDER_DELETED_ITEMS = 3


class OutlookComProvider(BaseMailProvider):
    """Integrates directly with the local Outlook Desktop Client via MAPI."""

    def __init__(self):
        self._app = None
        self._namespace = None

    def _ensure_connected(self):
        """Initializes COM and connects to Outlook application."""
        pythoncom.CoInitialize()
        if self._app is None:
            try:
                self._app = win32com.client.GetActiveObject("Outlook.Application")
            except Exception:
                self._app = win32com.client.Dispatch("Outlook.Application")
            self._namespace = self._app.GetNamespace("MAPI")

    def is_available(self) -> bool:
        """Checks if Outlook Desktop is installed and reachable via COM."""
        try:
            self._ensure_connected()
            return self._namespace is not None
        except Exception:
            return False

    def list_accounts(self) -> List[AccountInfo]:
        """Lists all configured mailbox accounts and shared stores in Outlook."""
        self._ensure_connected()
        accounts: List[AccountInfo] = []

        try:
            # Check configured stores
            for i in range(1, self._namespace.Stores.Count + 1):
                store = self._namespace.Stores.Item(i)
                store_id = store.StoreID
                display_name = store.DisplayName
                accounts.append(
                    AccountInfo(
                        id=store_id,
                        name=display_name,
                        email_address=display_name,
                        is_default=(i == 1),
                        store_type="Exchange/Office 365" if store.ExchangeStoreType != 0 else "PST/IMAP",
                    )
                )
        except Exception as ex:
            logger.warning("Error enumerating Outlook stores: %s", ex)
            # Fallback to root folders if Stores collection fails
            try:
                for i in range(1, self._namespace.Folders.Count + 1):
                    folder = self._namespace.Folders.Item(i)
                    accounts.append(
                        AccountInfo(
                            id=folder.StoreID,
                            name=folder.Name,
                            email_address=folder.Name,
                            is_default=(i == 1),
                        )
                    )
            except Exception as e2:
                logger.error("Failed to list accounts from root folders: %s", e2)

        return accounts

    def list_folders(self, account_id: str) -> List[FolderInfo]:
        """Recursively lists mail folders for a given store/account."""
        self._ensure_connected()
        folders_list: List[FolderInfo] = []

        root_folder = None
        for i in range(1, self._namespace.Folders.Count + 1):
            f = self._namespace.Folders.Item(i)
            if f.StoreID == account_id or f.Name == account_id:
                root_folder = f
                break

        if not root_folder and self._namespace.Folders.Count > 0:
            root_folder = self._namespace.Folders.Item(1)

        if root_folder:
            self._traverse_folders(root_folder, "", folders_list)

        return folders_list

    def _traverse_folders(self, parent_folder: Any, current_path: str, results: List[FolderInfo]):
        for i in range(1, parent_folder.Folders.Count + 1):
            child = parent_folder.Folders.Item(i)
            folder_path = f"{current_path}/{child.Name}".lstrip("/")
            is_inbox = "posteingang" in child.Name.lower() or "inbox" in child.Name.lower()

            item_count = 0
            unread_count = 0
            try:
                item_count = child.Items.Count
                unread_count = child.UnReadItemCount
            except Exception:
                pass

            results.append(
                FolderInfo(
                    id=child.EntryID,
                    name=child.Name,
                    path=folder_path,
                    item_count=item_count,
                    unread_count=unread_count,
                    is_inbox=is_inbox,
                )
            )
            # Recurse subfolders
            try:
                if child.Folders.Count > 0:
                    self._traverse_folders(child, folder_path, results)
            except Exception:
                pass

    def fetch_emails(
        self,
        account_id: str,
        folder_paths: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        max_count: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[EmailItem]:
        """Fetches email items from specified folders."""
        self._ensure_connected()
        emails: List[EmailItem] = []

        for folder_path in folder_paths:
            folder_obj = self._resolve_folder_by_path(account_id, folder_path)
            if not folder_obj:
                continue

            items = folder_obj.Items
            total_in_folder = items.Count
            logger.info("Scanning folder '%s' with %d items...", folder_path, total_in_folder)

            for idx in range(1, total_in_folder + 1):
                if max_count and len(emails) >= max_count:
                    break

                try:
                    item = items.Item(idx)
                    # Skip non-mail items (e.g. appointments or report items)
                    if item.Class != 43:  # 43 = olMail
                        continue

                    recv_time = None
                    try:
                        # Convert PyTime/datetime
                        rt = item.ReceivedTime
                        if isinstance(rt, datetime):
                            recv_time = ensure_utc(rt)
                        else:
                            recv_time = ensure_utc(datetime(rt.year, rt.month, rt.day, rt.hour, rt.minute, rt.second, tzinfo=timezone.utc))
                    except Exception:
                        recv_time = datetime.now(timezone.utc)

                    if recv_time is None:
                        recv_time = datetime.now(timezone.utc)

                    if date_from and recv_time < (ensure_utc(date_from) or date_from):
                        continue
                    if date_to and recv_time > (ensure_utc(date_to) or date_to):
                        continue

                    # Parse headers for List-Unsubscribe
                    headers = self._extract_headers(item)

                    importance_str = "normal"
                    if item.Importance == 2:
                        importance_str = "high"
                    elif item.Importance == 0:
                        importance_str = "low"

                    categories_list = [c.strip() for c in (item.Categories or "").split(",") if c.strip()]

                    body_raw = getattr(item, "Body", "") or ""
                    html_raw = getattr(item, "HTMLBody", "") or ""
                    email_item = EmailItem(
                        id=f"{item.EntryID}_{idx}",
                        entry_id=item.EntryID,
                        store_id=account_id,
                        account_name=account_id,
                        subject=item.Subject or "(Kein Betreff)",
                        sender_name=getattr(item, "SenderName", "") or "",
                        sender_email=getattr(item, "SenderEmailAddress", "") or "",
                        received_time=recv_time,
                        body_preview=(body_raw[:300] if body_raw else ""),
                        body_text=body_raw,
                        body_html=html_raw,
                        is_read=not bool(item.UnRead),
                        importance=importance_str,
                        categories=categories_list,
                        folder_path=folder_path,
                        size_bytes=getattr(item, "Size", 0) or 0,
                        headers=headers,
                    )
                    emails.append(email_item)

                    if progress_callback:
                        progress_callback(len(emails), total_in_folder)

                except Exception as ex:
                    logger.debug("Skipping item %d due to error: %s", idx, ex)

        return emails

    def _extract_headers(self, mail_item: Any) -> Dict[str, str]:
        """Extracts Internet transport headers using MAPI PropertyAccessor."""
        headers_dict: Dict[str, str] = {}
        try:
            prop_accessor = mail_item.PropertyAccessor
            raw_headers = prop_accessor.GetProperty(PR_TRANSPORT_MESSAGE_HEADERS)
            if raw_headers:
                for line in raw_headers.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers_dict[k.strip()] = v.strip()
        except Exception:
            pass
        return headers_dict

    def _resolve_folder_by_path(self, account_id: str, path: str) -> Optional[Any]:
        """Finds a COM folder object by matching its path."""
        root_folder = None
        for i in range(1, self._namespace.Folders.Count + 1):
            f = self._namespace.Folders.Item(i)
            if f.StoreID == account_id or f.Name == account_id:
                root_folder = f
                break

        if not root_folder and self._namespace.Folders.Count > 0:
            root_folder = self._namespace.Folders.Item(1)

        if not root_folder:
            return None

        parts = path.strip("/").split("/")
        current = root_folder
        for part in parts:
            found = False
            for j in range(1, current.Folders.Count + 1):
                sub = current.Folders.Item(j)
                if sub.Name.lower() == part.lower():
                    current = sub
                    found = True
                    break
            if not found:
                return None
        return current

    def _get_or_create_folder(self, account_id: str, path: str) -> Optional[Any]:
        """Finds or creates a folder path in the store."""
        root_folder = None
        for i in range(1, self._namespace.Folders.Count + 1):
            f = self._namespace.Folders.Item(i)
            if f.StoreID == account_id or f.Name == account_id:
                root_folder = f
                break

        if not root_folder and self._namespace.Folders.Count > 0:
            root_folder = self._namespace.Folders.Item(1)

        if not root_folder:
            return None

        parts = path.strip("/").split("/")
        current = root_folder
        for part in parts:
            found = None
            for j in range(1, current.Folders.Count + 1):
                sub = current.Folders.Item(j)
                if sub.Name.lower() == part.lower():
                    found = sub
                    break
            if not found:
                # Create folder
                found = current.Folders.Add(part)
            current = found
        return current

    def execute_action(self, action: PlannedAction, account_id: str) -> ExecutionResult:
        """Executes a single action in Outlook."""
        self._ensure_connected()
        try:
            item = self._namespace.GetItemFromID(action.email_id.split("_")[0], account_id)
        except Exception as ex:
            return ExecutionResult(
                action=action,
                success=False,
                message=f"E-Mail mit EntryID konnte nicht geöffnet werden: {ex}",
            )

        executed_changes = []
        try:
            # 1. Target Folder Move
            if action.target_folder:
                if action.target_folder in ("Gelöschte Elemente", "Trash", "Papierkorb"):
                    deleted_folder = self._namespace.GetDefaultFolder(OL_FOLDER_DELETED_ITEMS)
                    item = item.Move(deleted_folder)
                    executed_changes.append("In Gelöschte Elemente verschoben")
                else:
                    dest = self._get_or_create_folder(account_id, action.target_folder)
                    if dest:
                        item = item.Move(dest)
                        executed_changes.append(f"Verschoben nach '{action.target_folder}'")
                    else:
                        return ExecutionResult(action=action, success=False, message=f"Zielordner '{action.target_folder}' konnte nicht erstellt werden")

            # 2. Read state
            if action.mark_as_read and item.UnRead:
                item.UnRead = False
                item.Save()
                executed_changes.append("Als gelesen markiert")
            elif action.mark_as_unread and not item.UnRead:
                item.UnRead = True
                item.Save()
                executed_changes.append("Als ungelesen markiert")

            # 3. Categories
            if action.add_category:
                cats = [c.strip() for c in (item.Categories or "").split(",") if c.strip()]
                if action.add_category not in cats:
                    cats.append(action.add_category)
                    item.Categories = ", ".join(cats)
                    item.Save()
                    executed_changes.append(f"Kategorie '{action.add_category}' zugewiesen")

            return ExecutionResult(
                action=action,
                success=True,
                is_dry_run=False,
                message=", ".join(executed_changes) if executed_changes else "Keine Änderungen nötig",
            )
        except Exception as ex:
            return ExecutionResult(
                action=action,
                success=False,
                message=f"Fehler bei Ausführung in Outlook: {str(ex)}",
            )

    def restore_item(
        self,
        entry_id: str,
        store_id: str,
        target_folder: str,
        is_read: bool,
        categories: List[str],
    ) -> None:
        """Restores an item back to its original folder and properties during rollback."""
        self._ensure_connected()
        item = self._namespace.GetItemFromID(entry_id, store_id)
        dest_folder = self._get_or_create_folder(store_id, target_folder)
        if dest_folder:
            item = item.Move(dest_folder)
        item.UnRead = not is_read
        item.Categories = ", ".join(categories)
        item.Save()
