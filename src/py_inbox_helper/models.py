"""Domain models for email analysis, action planning, and snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import re


class ActionType(str, Enum):
    """Types of actions that can be performed on an email item."""
    NONE = "NONE"
    MOVE = "MOVE"
    MARK_READ = "MARK_READ"
    MARK_UNREAD = "MARK_UNREAD"
    MOVE_AND_MARK_READ = "MOVE_AND_MARK_READ"
    MARK_IMPORTANT = "MARK_IMPORTANT"
    MARK_RESUBMISSION = "MARK_RESUBMISSION"  # Wiedervorlage / Follow-up
    TRASH = "TRASH"  # Move to Deleted Items (soft delete)


class EmailCategory(str, Enum):
    """Heuristic categories assigned to emails."""
    UNCLASSIFIED = "UNCLASSIFIED"
    NEWSLETTER = "NEWSLETTER"
    INVOICE_FINANCE = "INVOICE_FINANCE"
    NOTIFICATION = "NOTIFICATION"
    IMPORTANT_ACTION = "IMPORTANT_ACTION"
    RESUBMISSION = "RESUBMISSION"  # Wiedervorlage
    ARCHIVE_OLD = "ARCHIVE_OLD"
    JUNK = "JUNK"


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime object is timezone-aware and normalized to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class EmailItem:
    """Represents an email item retrieved from a mailbox provider."""
    id: str
    entry_id: str
    store_id: str
    account_name: str
    subject: str
    sender_name: str
    sender_email: str
    received_time: datetime
    body_preview: str = ""
    is_read: bool = False
    importance: str = "normal"  # low, normal, high
    categories: List[str] = field(default_factory=list)
    folder_path: str = "Posteingang"
    size_bytes: int = 0
    headers: Dict[str, str] = field(default_factory=dict)
    assigned_category: EmailCategory = EmailCategory.UNCLASSIFIED
    classification_reason: str = ""

    def __post_init__(self):
        if self.received_time is not None:
            self.received_time = ensure_utc(self.received_time)

    @property
    def has_unsubscribe_header(self) -> bool:
        """Check if email contains List-Unsubscribe header."""
        for key in self.headers:
            if key.lower() == "list-unsubscribe":
                return True
        return False

    @property
    def unsubscribe_url(self) -> Optional[str]:
        """Extract HTTP/HTTPS unsubscribe link from headers or preview."""
        header_val = self._get_header_val("list-unsubscribe")
        if header_val:
            matches = re.findall(r'<https?://[^>]+>', header_val)
            if matches:
                return matches[0].strip("<>")
            plain_matches = re.findall(r'https?://[^\s,;<>"\']+', header_val)
            if plain_matches:
                return plain_matches[0]
        return None

    @property
    def unsubscribe_mailto(self) -> Optional[str]:
        """Extract mailto unsubscribe address from headers."""
        header_val = self._get_header_val("list-unsubscribe")
        if header_val:
            matches = re.findall(r'<mailto:[^>]+>', header_val)
            if matches:
                return matches[0].strip("<>")
            plain_matches = re.findall(r'mailto:[^\s,;<>"\']+', header_val)
            if plain_matches:
                return plain_matches[0]
        return None

    @property
    def is_one_click_unsubscribe(self) -> bool:
        """Check if email supports RFC 8058 One-Click unsubscription."""
        post_header = self._get_header_val("list-unsubscribe-post")
        if post_header and "list-unsubscribe=one-click" in post_header.lower():
            return bool(self.unsubscribe_url)
        return False

    def _get_header_val(self, header_name: str) -> Optional[str]:
        target = header_name.lower()
        for k, v in self.headers.items():
            if k.lower() == target:
                return v
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "store_id": self.store_id,
            "account_name": self.account_name,
            "subject": self.subject,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "received_time": self.received_time.isoformat(),
            "body_preview": self.body_preview,
            "is_read": self.is_read,
            "importance": self.importance,
            "categories": self.categories,
            "folder_path": self.folder_path,
            "size_bytes": self.size_bytes,
            "headers": self.headers,
            "assigned_category": self.assigned_category.value,
            "classification_reason": self.classification_reason,
        }


@dataclass
class PlannedAction:
    """Represents a planned action to be previewed or executed."""
    email_id: str
    email_subject: str
    action_type: ActionType = ActionType.NONE
    target_folder: Optional[str] = None
    mark_as_read: bool = False
    mark_as_unread: bool = False
    set_flag: Optional[str] = None
    add_category: Optional[str] = None
    unsubscribe: bool = False
    unsubscribe_url: Optional[str] = None
    unsubscribe_mailto: Optional[str] = None
    explanation: str = ""
    is_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email_id": self.email_id,
            "email_subject": self.email_subject,
            "action_type": self.action_type.value,
            "target_folder": self.target_folder,
            "mark_as_read": self.mark_as_read,
            "mark_as_unread": self.mark_as_unread,
            "set_flag": self.set_flag,
            "add_category": self.add_category,
            "unsubscribe": self.unsubscribe,
            "unsubscribe_url": self.unsubscribe_url,
            "unsubscribe_mailto": self.unsubscribe_mailto,
            "explanation": self.explanation,
            "is_enabled": self.is_enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlannedAction:
        return cls(
            email_id=data["email_id"],
            email_subject=data.get("email_subject", ""),
            action_type=ActionType(data.get("action_type", ActionType.NONE.value)),
            target_folder=data.get("target_folder"),
            mark_as_read=data.get("mark_as_read", False),
            mark_as_unread=data.get("mark_as_unread", False),
            set_flag=data.get("set_flag"),
            add_category=data.get("add_category"),
            unsubscribe=data.get("unsubscribe", False),
            unsubscribe_url=data.get("unsubscribe_url"),
            unsubscribe_mailto=data.get("unsubscribe_mailto"),
            explanation=data.get("explanation", ""),
            is_enabled=data.get("is_enabled", True),
        )


@dataclass
class ActionPlan:
    """A collection of planned actions for a cleanup run."""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    account_name: str = ""
    actions: List[PlannedAction] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.actions)

    @property
    def enabled_count(self) -> int:
        return sum(1 for a in self.actions if a.is_enabled)


@dataclass
class BackupItemState:
    """Snapshot state of a single email before modifications."""
    id: str
    entry_id: str
    store_id: str
    folder_path: str
    is_read: bool
    importance: str
    categories: List[str]
    subject: str


@dataclass
class BackupSnapshot:
    """Full snapshot taken immediately before executing changes."""
    snapshot_id: str
    created_at: datetime
    account_name: str
    items: List[BackupItemState] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "account_name": self.account_name,
            "items": [
                {
                    "id": item.id,
                    "entry_id": item.entry_id,
                    "store_id": item.store_id,
                    "folder_path": item.folder_path,
                    "is_read": item.is_read,
                    "importance": item.importance,
                    "categories": item.categories,
                    "subject": item.subject,
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BackupSnapshot:
        return cls(
            snapshot_id=data["snapshot_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            account_name=data["account_name"],
            items=[
                BackupItemState(
                    id=i["id"],
                    entry_id=i["entry_id"],
                    store_id=i["store_id"],
                    folder_path=i["folder_path"],
                    is_read=i["is_read"],
                    importance=i["importance"],
                    categories=i.get("categories", []),
                    subject=i.get("subject", ""),
                )
                for i in data.get("items", [])
            ],
        )


@dataclass
class ExecutionResult:
    """Result of an action execution (or dry-run simulation)."""
    action: PlannedAction
    success: bool
    is_dry_run: bool = False
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
