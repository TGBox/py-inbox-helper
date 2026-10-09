"""Storage analysis and sender clustering for batch cleanup operations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from py_inbox_helper.models import EmailItem


def format_bytes(size_bytes: int) -> str:
    """Formats bytes into human-readable strings (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@dataclass
class SenderCluster:
    """Aggregated group of emails sharing the same sender address."""
    sender_email: str
    sender_name: str
    email_count: int
    unread_count: int
    total_size_bytes: int
    has_unsubscribe: bool
    sample_subjects: List[str] = field(default_factory=list)
    email_ids: List[str] = field(default_factory=list)

    @property
    def formatted_size(self) -> str:
        return format_bytes(self.total_size_bytes)


class StorageAnalyzer:
    """Analyzes email storage footprint and clusters messages by sender."""

    def cluster_by_sender(self, emails: List[EmailItem]) -> List[SenderCluster]:
        """Clusters emails by sender address, ordered by message count descending."""
        clusters_map: Dict[str, Dict] = {}

        for email in emails:
            key = (email.sender_email or "").strip().lower()
            if not key:
                key = "unbekannt@domain.local"

            if key not in clusters_map:
                clusters_map[key] = {
                    "sender_email": key,
                    "sender_name": email.sender_name or key,
                    "email_count": 0,
                    "unread_count": 0,
                    "total_size_bytes": 0,
                    "has_unsubscribe": False,
                    "sample_subjects": [],
                    "email_ids": [],
                }

            c = clusters_map[key]
            c["email_count"] += 1
            if not email.is_read:
                c["unread_count"] += 1
            c["total_size_bytes"] += email.size_bytes
            if email.has_unsubscribe_header:
                c["has_unsubscribe"] = True
            if len(c["sample_subjects"]) < 3 and email.subject:
                c["sample_subjects"].append(email.subject)
            c["email_ids"].append(email.id)

        results = [
            SenderCluster(
                sender_email=data["sender_email"],
                sender_name=data["sender_name"],
                email_count=data["email_count"],
                unread_count=data["unread_count"],
                total_size_bytes=data["total_size_bytes"],
                has_unsubscribe=data["has_unsubscribe"],
                sample_subjects=data["sample_subjects"],
                email_ids=data["email_ids"],
            )
            for data in clusters_map.values()
        ]

        # Sort by email count descending, then total size descending
        results.sort(key=lambda x: (x.email_count, x.total_size_bytes), reverse=True)
        return results

    def get_large_emails(self, emails: List[EmailItem], min_bytes: int = 5_000_000) -> List[EmailItem]:
        """Filters emails exceeding min_bytes threshold, sorted by size descending."""
        large = [e for e in emails if e.size_bytes >= min_bytes]
        large.sort(key=lambda e: e.size_bytes, reverse=True)
        return large
