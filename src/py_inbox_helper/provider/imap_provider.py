"""Generic IMAP mail provider supporting Gmail, GMX, Web.de and custom servers."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import email
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
import imaplib
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional
import uuid

from py_inbox_helper.models import EmailItem, ExecutionResult, PlannedAction, ensure_utc
from py_inbox_helper.provider.base import AccountInfo, BaseMailProvider, FolderInfo

logger = logging.getLogger(__name__)


def decode_imap_utf7(s: str) -> str:
    """Decodes an IMAP modified UTF-7 string according to RFC 3501 Section 5.1.3."""
    if not s:
        return ""

    def _replace(match: re.Match) -> str:
        b64_str = match.group(1)
        if not b64_str:
            # "&-" represents literal "&"
            return "&"
        # In modified UTF-7, comma replaces slash
        std_b64 = b64_str.replace(",", "/")
        # Pad with '=' to multiple of 4
        rem = len(std_b64) % 4
        if rem != 0:
            std_b64 += "=" * (4 - rem)
        try:
            raw_bytes = base64.b64decode(std_b64)
            return raw_bytes.decode("utf-16-be")
        except Exception:
            return match.group(0)

    # Match &...- where ... is empty or base64 characters with comma instead of slash
    return re.sub(r"&([A-Za-z0-9+,]*)-", _replace, s)


from py_inbox_helper.security import delete_secret, get_secret, store_secret

@dataclass
class ImapConfig:
    """Connection credentials for an IMAP mailbox account."""
    profile_id: str
    account_name: str
    host: str
    port: int = 993
    use_ssl: bool = True
    username: str = ""
    password: str = ""

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "account_name": self.account_name,
            "host": self.host,
            "port": self.port,
            "use_ssl": self.use_ssl,
            "username": self.username,
            "password": self.password if include_secrets else "",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImapConfig:
        return cls(
            profile_id=data.get("profile_id", str(uuid.uuid4())),
            account_name=data.get("account_name", "IMAP Konto"),
            host=data.get("host", ""),
            port=data.get("port", 993),
            use_ssl=data.get("use_ssl", True),
            username=data.get("username", ""),
            password=data.get("password", ""),
        )


class ImapProfileManager:
    """Stores and retrieves IMAP connection profiles in local JSON file with keyring credentials."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            self.config_path = Path.home() / ".py_inbox_helper" / "imap_profiles.json"
        else:
            self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> List[ImapConfig]:
        if not self.config_path.exists():
            return []
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = [ImapConfig.from_dict(item) for item in data]
            needs_resave = False
            for p in profiles:
                secret = get_secret(f"imap_{p.profile_id}")
                if secret:
                    p.password = secret
                elif p.password:
                    # Legacy plaintext password found in JSON: migrate to keyring and scrub
                    store_secret(f"imap_{p.profile_id}", p.password)
                    needs_resave = True

            if needs_resave:
                self._save_raw_profiles(profiles)
            return profiles
        except Exception as ex:
            logger.warning("Could not load IMAP profiles: %s", ex)
            return []

    def _save_raw_profiles(self, profiles: List[ImapConfig]) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump([p.to_dict(include_secrets=False) for p in profiles], f, indent=2)

    def save_profile(self, profile: ImapConfig) -> None:
        if profile.password:
            store_secret(f"imap_{profile.profile_id}", profile.password)
        profiles = [p for p in self.list_profiles() if p.profile_id != profile.profile_id]
        profiles.append(profile)
        self._save_raw_profiles(profiles)

    def delete_profile(self, profile_id: str) -> None:
        delete_secret(f"imap_{profile_id}")
        profiles = [p for p in self.list_profiles() if p.profile_id != profile_id]
        self._save_raw_profiles(profiles)


class ImapMailProvider(BaseMailProvider):
    """Accesses IMAP accounts via imaplib."""

    def __init__(self, profile_manager: Optional[ImapProfileManager] = None):
        self.profile_manager = profile_manager or ImapProfileManager()

    def _connect(self, config: ImapConfig) -> imaplib.IMAP4:
        if config.use_ssl:
            client = imaplib.IMAP4_SSL(config.host, config.port)
        else:
            client = imaplib.IMAP4(config.host, config.port)
        client.login(config.username, config.password)
        return client

    def _get_profile(self, account_id: str) -> Optional[ImapConfig]:
        for p in self.profile_manager.list_profiles():
            if p.profile_id == account_id:
                return p
        return None

    def list_accounts(self) -> List[AccountInfo]:
        profiles = self.profile_manager.list_profiles()
        return [
            AccountInfo(
                id=p.profile_id,
                name=p.account_name,
                email_address=p.username,
                is_default=(i == 0),
                store_type="IMAP",
            )
            for i, p in enumerate(profiles)
        ]

    def list_folders(self, account_id: str) -> List[FolderInfo]:
        profile = self._get_profile(account_id)
        if not profile:
            return []

        folders: List[FolderInfo] = []
        try:
            client = self._connect(profile)
            status, raw_folders = client.list()
            client.logout()

            if status == "OK" and raw_folders:
                for line in raw_folders:
                    if isinstance(line, bytes):
                        line_str = line.decode("latin1", errors="replace")
                        match = re.search(r'\((?P<flags>[^)]*)\)\s+(?:"(?P<delim>[^"]+)"|NIL)\s+(?P<name>.*)$', line_str)
                        if match:
                            raw_name = match.group("name").strip().strip('"')
                        else:
                            parts = line_str.split(' "/" ')
                            raw_name = parts[-1].strip().strip('"') if len(parts) > 1 else line_str
                        decoded_name = decode_imap_utf7(raw_name)
                        is_inbox = "inbox" in decoded_name.lower() or "posteingang" in decoded_name.lower()
                        folders.append(
                            FolderInfo(
                                id=raw_name,
                                name=decoded_name,
                                path=raw_name,
                                is_inbox=is_inbox,
                            )
                        )
        except Exception as ex:
            logger.error("Failed to list IMAP folders: %s", ex)

        return folders

    def fetch_emails(
        self,
        account_id: str,
        folder_paths: List[str],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        max_count: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[EmailItem]:
        profile = self._get_profile(account_id)
        if not profile:
            return []

        emails: List[EmailItem] = []
        try:
            client = self._connect(profile)
            for folder in folder_paths:
                status, _ = client.select(f'"{folder}"', readonly=True)
                if status != "OK":
                    continue

                status, data = client.search(None, "ALL")
                if status != "OK" or not data[0]:
                    continue

                msg_ids = data[0].split()
                total = len(msg_ids)

                for idx, mid in enumerate(reversed(msg_ids)):
                    if max_count and len(emails) >= max_count:
                        break

                    res, msg_data = client.fetch(mid, "(RFC822.HEADER RFC822.SIZE INTERNALDATE FLAGS)")
                    if res != "OK":
                        continue

                    raw_header = b""
                    meta_info = b""
                    for part in msg_data:
                        if isinstance(part, tuple):
                            meta_info += part[0] + b" "
                            raw_header = part[1]
                        elif isinstance(part, bytes):
                            meta_info += part + b" "

                    msg = email.message_from_bytes(raw_header)
                    subject = self._decode_mime_str(msg.get("Subject", "(Kein Betreff)"))

                    raw_from = msg.get("From", "")
                    name_raw, addr_raw = parseaddr(raw_from)
                    decoded_sender_name = self._decode_mime_str(name_raw).strip()
                    decoded_sender_email = self._decode_mime_str(addr_raw).strip()
                    if not decoded_sender_name and not decoded_sender_email:
                        decoded_sender_name = self._decode_mime_str(raw_from).strip() or "(Unbekannt)"
                        decoded_sender_email = decoded_sender_name
                    elif not decoded_sender_name:
                        decoded_sender_name = decoded_sender_email
                    elif not decoded_sender_email:
                        decoded_sender_email = decoded_sender_name

                    size_bytes = 0
                    meta_str = meta_info.decode("latin1", errors="replace")
                    size_match = re.search(r'RFC822\.SIZE\s+(\d+)', meta_str, re.IGNORECASE)
                    if size_match:
                        size_bytes = int(size_match.group(1))

                    received_time: Optional[datetime] = None
                    date_header = msg.get("Date")
                    if date_header:
                        try:
                            received_time = parsedate_to_datetime(date_header)
                        except Exception:
                            received_time = None

                    if not received_time:
                        internal_match = re.search(r'INTERNALDATE\s+"([^"]+)"', meta_str, re.IGNORECASE)
                        if internal_match:
                            try:
                                received_time = parsedate_to_datetime(internal_match.group(1))
                            except Exception:
                                received_time = None

                    if not received_time:
                        received_time = datetime.now(timezone.utc)
                    else:
                        received_time = ensure_utc(received_time)

                    if date_from and received_time < (ensure_utc(date_from) or date_from):
                        continue
                    if date_to and received_time > (ensure_utc(date_to) or date_to):
                        continue

                    is_read = b"\\Seen" in meta_info

                    # Extract Headers
                    headers_dict = {}
                    for h_key in msg.keys():
                        headers_dict[h_key] = msg.get(h_key, "")

                    decoded_folder_display = decode_imap_utf7(folder)

                    item = EmailItem(
                        id=f"{account_id}_{folder}_{mid.decode()}",
                        entry_id=mid.decode(),
                        store_id=account_id,
                        account_name=profile.account_name,
                        subject=subject,
                        sender_name=decoded_sender_name,
                        sender_email=decoded_sender_email,
                        received_time=received_time,
                        body_preview=subject,
                        is_read=is_read,
                        folder_path=decoded_folder_display,
                        size_bytes=size_bytes,
                        headers=headers_dict,
                    )
                    emails.append(item)
                    if progress_callback:
                        progress_callback(len(emails), total)

            client.logout()
        except Exception as ex:
            logger.error("Error fetching IMAP emails: %s", ex)

        return emails

    def _decode_mime_str(self, val: str) -> str:
        decoded_fragments = decode_header(val)
        result = []
        for text, encoding in decoded_fragments:
            if isinstance(text, bytes):
                try:
                    result.append(text.decode(encoding or "utf-8", errors="replace"))
                except Exception:
                    result.append(text.decode("latin1", errors="replace"))
            else:
                result.append(str(text))
        return "".join(result)

    def execute_action(self, action: PlannedAction, account_id: str) -> ExecutionResult:
        profile = self._get_profile(account_id)
        if not profile:
            return ExecutionResult(action=action, success=False, message="Profil nicht gefunden")

        try:
            client = self._connect(profile)
            msg_id = action.email_id.split("_")[-1]

            if action.mark_as_read:
                client.store(msg_id, "+FLAGS", "(\\Seen)")
            elif action.mark_as_unread:
                client.store(msg_id, "-FLAGS", "(\\Seen)")

            if action.target_folder:
                # Copy to target and mark deleted
                client.create(f'"{action.target_folder}"')
                client.copy(msg_id, f'"{action.target_folder}"')
                client.store(msg_id, "+FLAGS", "(\\Deleted)")
                client.expunge()

            client.logout()
            return ExecutionResult(action=action, success=True, message="IMAP-Aktion ausgeführt")
        except Exception as ex:
            return ExecutionResult(action=action, success=False, message=f"IMAP-Fehler: {ex}")

    def restore_item(
        self,
        entry_id: str,
        store_id: str,
        target_folder: str,
        is_read: bool,
        categories: List[str],
    ) -> None:
        profile = self._get_profile(store_id)
        if not profile:
            return

        client = self._connect(profile)
        if is_read:
            client.store(entry_id, "+FLAGS", "(\\Seen)")
        else:
            client.store(entry_id, "-FLAGS", "(\\Seen)")
        client.logout()
