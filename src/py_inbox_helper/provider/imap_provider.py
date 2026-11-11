"""Generic IMAP mail provider supporting Gmail, GMX, Web.de and custom servers."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import email
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
import imaplib
import json
import logging
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple
import uuid

from py_inbox_helper.models import EmailItem, ExecutionResult, PlannedAction, ensure_utc
from py_inbox_helper.provider.base import AccountInfo, BaseMailProvider, FolderInfo

logger = logging.getLogger(__name__)

# Folder names (lower-case) that mean "the mailbox's trash folder".
TRASH_ALIASES = {
    "gelöschte elemente", "gelöschte objekte", "gelöscht", "papierkorb",
    "trash", "bin", "deleted items", "deleted messages",
}

# Number of messages requested per FETCH command during a scan.
FETCH_CHUNK_SIZE = 200

_IMAP_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class ImapActionError(Exception):
    """An IMAP operation could not be carried out; the message is shown to the user."""


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


def encode_imap_utf7(s: str) -> str:
    """Encodes a string to IMAP modified UTF-7 (RFC 3501 Section 5.1.3)."""
    result: List[str] = []
    pending: List[str] = []

    def _flush() -> None:
        if pending:
            raw = "".join(pending).encode("utf-16-be")
            b64 = base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",")
            result.append(f"&{b64}-")
            pending.clear()

    for ch in s:
        if 0x20 <= ord(ch) <= 0x7E:
            _flush()
            result.append("&-" if ch == "&" else ch)
        else:
            pending.append(ch)
    _flush()
    return "".join(result)


def _quote(mailbox: str) -> str:
    """Quotes a (modified UTF-7 encoded) mailbox name for use in an IMAP command."""
    return '"' + mailbox.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _imap_date(dt: datetime) -> str:
    """Formats a date for IMAP SEARCH (locale independent)."""
    return f"{dt.day:02d}-{_IMAP_MONTHS[dt.month - 1]}-{dt.year}"


def _parse_list_line(line: Any) -> Optional[Tuple[Set[str], Optional[str], str]]:
    """Parses one LIST response line into (flags, hierarchy delimiter, raw mailbox name)."""
    literal_name: Optional[str] = None
    if isinstance(line, tuple):
        # Mailbox name was sent as a literal: (b'(flags) "/" {n}', b'name')
        literal_name = line[1].decode("latin1", errors="replace")
        line = line[0]
    if not isinstance(line, bytes):
        return None
    line_str = line.decode("latin1", errors="replace")
    match = re.match(r'\s*\((?P<flags>[^)]*)\)\s+(?:"(?P<delim>(?:[^"\\]|\\.)+)"|NIL)\s*(?P<name>.*)$', line_str)
    if not match:
        return None
    flags = {f.lower() for f in match.group("flags").split()}
    delim = match.group("delim")
    if delim:
        delim = delim.replace("\\\\", "\\").replace('\\"', '"')
    if literal_name is not None:
        name = literal_name
    else:
        name = match.group("name").strip()
        if len(name) >= 2 and name.startswith('"') and name.endswith('"'):
            name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if not name:
        return None
    return flags, delim, name


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


@dataclass
class _ImapSession:
    """An open, authenticated connection that is reused for a whole execution run."""
    account_id: str
    client: Any
    capabilities: Set[str] = field(default_factory=set)
    delimiter: str = "/"
    namespace_prefix: str = ""
    trash_folder: Optional[str] = None          # raw (modified UTF-7) name
    known_folders: Set[str] = field(default_factory=set)  # raw names
    selected: Optional[str] = None
    selected_readonly: bool = True
    uidvalidity: Optional[str] = None


class ImapMailProvider(BaseMailProvider):
    """Accesses IMAP accounts via imaplib.

    Messages are always addressed by UID (stable) and never by sequence number
    (which shifts whenever a message is moved or expunged).

    Email ids have the form ``<account_id>_<raw folder>_<uidvalidity>-<uid>``;
    ``entry_id`` is the UID inside that folder.
    """

    def __init__(self, profile_manager: Optional[ImapProfileManager] = None):
        self.profile_manager = profile_manager or ImapProfileManager()
        self._session: Optional[_ImapSession] = None

    # ------------------------------------------------------------------ #
    # Connection handling
    # ------------------------------------------------------------------ #
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

    def _get_session(self, account_id: str) -> _ImapSession:
        """Returns the cached connection for the account or opens a new one."""
        if self._session is not None and self._session.account_id == account_id:
            return self._session
        self.close()

        profile = self._get_profile(account_id)
        if not profile:
            raise ImapActionError("IMAP-Profil nicht gefunden")
        try:
            client = self._connect(profile)
        except (imaplib.IMAP4.error, OSError) as ex:
            raise ImapActionError(f"IMAP-Anmeldung fehlgeschlagen: {ex}") from ex

        session = _ImapSession(account_id=account_id, client=client)

        # Capabilities after login (servers often announce more once authenticated)
        try:
            typ, data = client.capability()
            if typ == "OK" and data and isinstance(data[0], bytes):
                session.capabilities = {c.upper() for c in data[0].decode("ascii", errors="replace").split()}
        except Exception as ex:
            logger.debug("CAPABILITY failed: %s", ex)

        # Personal namespace prefix (e.g. "INBOX." on Courier / some Dovecot setups)
        if "NAMESPACE" in session.capabilities:
            try:
                typ, data = client.namespace()
                if typ == "OK" and data and isinstance(data[0], bytes):
                    match = re.match(r'\s*\(\("((?:[^"\\]|\\.)*)"', data[0].decode("latin1", errors="replace"))
                    if match:
                        session.namespace_prefix = match.group(1)
            except Exception as ex:
                logger.debug("NAMESPACE failed: %s", ex)

        # Existing folders, hierarchy delimiter and trash folder
        typ, raw_folders = client.list()
        trash_by_name: Optional[str] = None
        if typ == "OK" and raw_folders:
            for line in raw_folders:
                parsed = _parse_list_line(line)
                if not parsed:
                    continue
                flags, delim, name = parsed
                session.known_folders.add(name)
                if delim:
                    session.delimiter = delim
                if "\\noselect" in flags:
                    continue
                if "\\trash" in flags:
                    session.trash_folder = name
                leaf = decode_imap_utf7(name).split(delim)[-1] if delim else decode_imap_utf7(name)
                if trash_by_name is None and leaf.strip().lower() in TRASH_ALIASES:
                    trash_by_name = name
        if session.trash_folder is None:
            session.trash_folder = trash_by_name

        self._session = session
        return session

    def close(self) -> None:
        """Closes the cached connection (if any)."""
        session, self._session = self._session, None
        if session is None:
            return
        try:
            session.client.logout()
        except Exception:
            pass

    def _drop_session(self) -> None:
        """Forgets a broken connection without talking to the server again."""
        session, self._session = self._session, None
        if session is not None:
            try:
                session.client.shutdown()
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Low-level helpers (all operate on UIDs)
    # ------------------------------------------------------------------ #
    def _select(self, session: _ImapSession, raw_folder: str, readonly: bool = False) -> None:
        if session.selected == raw_folder and session.selected_readonly == readonly:
            return
        session.selected = None
        typ, _ = session.client.select(_quote(raw_folder), readonly=readonly)
        if typ != "OK":
            raise ImapActionError(f"Ordner '{decode_imap_utf7(raw_folder)}' konnte nicht geöffnet werden")
        session.selected = raw_folder
        session.selected_readonly = readonly
        session.uidvalidity = self._read_uidvalidity(session.client)

    @staticmethod
    def _read_uidvalidity(client: Any) -> Optional[str]:
        try:
            typ, data = client.response("UIDVALIDITY")
        except Exception:
            return None
        if data and isinstance(data[0], bytes):
            match = re.search(rb"\d+", data[0])
            if match:
                return match.group(0).decode()
        return None

    def _fetch_message_id(self, session: _ImapSession, uid: str) -> str:
        """Verifies that the UID exists in the selected folder and returns its Message-ID ('' if none)."""
        typ, data = session.client.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if typ == "OK" and data:
            for part in data:
                if isinstance(part, tuple) and len(part) >= 2:
                    msg = email.message_from_bytes(part[1] or b"")
                    return (msg.get("Message-ID") or "").strip()
        raise ImapActionError(
            "E-Mail im Ordner nicht mehr gefunden (verschoben oder gelöscht?). Bitte Postfach neu scannen."
        )

    def _uid_store(self, session: _ImapSession, uid: str, operation: str, flags: str) -> None:
        typ, _ = session.client.uid("STORE", uid, operation, flags)
        if typ != "OK":
            raise ImapActionError(f"Kennzeichen {flags} konnten nicht gesetzt werden")

    def _resolve_target_folder(self, session: _ImapSession, target_folder: str) -> str:
        """Maps a configured target folder to the raw server mailbox name, creating it if needed."""
        wanted = target_folder.strip().strip("/")
        if wanted.lower() in TRASH_ALIASES:
            if not session.trash_folder:
                raise ImapActionError("Kein Papierkorb-Ordner auf dem IMAP-Server gefunden")
            return session.trash_folder

        if session.delimiter and session.delimiter != "/":
            wanted = wanted.replace("/", session.delimiter)
        raw = encode_imap_utf7(wanted)
        prefix = session.namespace_prefix
        if prefix and raw.upper() != "INBOX" and not raw.startswith(prefix):
            raw = prefix + raw
        self._ensure_folder(session, raw)
        return raw

    def _ensure_folder(self, session: _ImapSession, raw: str) -> None:
        if raw in session.known_folders or raw.upper() == "INBOX":
            return
        typ, data = session.client.create(_quote(raw))
        if typ != "OK":
            raise ImapActionError(
                f"Zielordner '{decode_imap_utf7(raw)}' konnte nicht angelegt werden"
            )
        try:
            session.client.subscribe(_quote(raw))
        except Exception:
            pass
        session.known_folders.add(raw)

    def _move(self, session: _ImapSession, uid: str, raw_target: str, message_id: str) -> Optional[str]:
        """Moves one message of the selected folder to ``raw_target``.

        Returns the message's UID in the target folder (None if it cannot be
        determined). The source message is only removed after the server has
        confirmed the copy.
        """
        client = session.client
        try:
            client.response("COPYUID")  # discard stale response data
        except Exception:
            pass

        if "MOVE" in session.capabilities:
            typ, _ = client.uid("MOVE", uid, _quote(raw_target))
            if typ != "OK":
                raise ImapActionError(
                    f"Verschieben nach '{decode_imap_utf7(raw_target)}' vom Server abgelehnt – E-Mail unverändert"
                )
        else:
            typ, _ = client.uid("COPY", uid, _quote(raw_target))
            if typ != "OK":
                raise ImapActionError(
                    f"Kopieren nach '{decode_imap_utf7(raw_target)}' vom Server abgelehnt – E-Mail wurde NICHT gelöscht"
                )
            self._uid_store(session, uid, "+FLAGS", "(\\Deleted)")
            if "UIDPLUS" in session.capabilities:
                # Removes exactly this message. A plain EXPUNGE would also purge
                # every other message the user has marked as deleted.
                client.uid("EXPUNGE", uid)

        new_uid: Optional[str] = None
        try:
            typ, data = client.response("COPYUID")
            if data and isinstance(data[0], bytes):
                parts = data[0].decode("ascii", errors="replace").split()
                if len(parts) >= 3 and parts[-1].isdigit():
                    new_uid = parts[-1]
        except Exception:
            new_uid = None

        if new_uid is None and message_id:
            new_uid = self._find_uid_by_message_id(session, raw_target, message_id)
        return new_uid

    def _find_uid_by_message_id(self, session: _ImapSession, raw_folder: str, message_id: str) -> Optional[str]:
        """Fallback for servers without UIDPLUS: locate a message by its Message-ID header."""
        try:
            self._select(session, raw_folder, readonly=True)
            typ, data = session.client.uid("SEARCH", None, "HEADER", "Message-ID", _quote(message_id))
            if typ == "OK" and data and isinstance(data[0], bytes) and data[0].split():
                return data[0].split()[-1].decode()
        except ImapActionError:
            pass
        return None

    def _parse_email_id(self, email_id: str, account_id: str) -> Tuple[str, str, str]:
        """Splits an email id into (raw folder, uidvalidity, uid)."""
        prefix = f"{account_id}_"
        if not email_id.startswith(prefix):
            raise ImapActionError("E-Mail gehört nicht zum ausgewählten IMAP-Konto")
        folder, sep, tail = email_id[len(prefix):].rpartition("_")
        match = re.fullmatch(r"(\d+)-(\d+)", tail)
        if not sep or not folder or not match:
            raise ImapActionError(
                "Diese Analyse stammt aus einer älteren Programmversion (ohne UIDs). Bitte Postfach neu scannen."
            )
        return folder, match.group(1), match.group(2)

    # ------------------------------------------------------------------ #
    # BaseMailProvider interface
    # ------------------------------------------------------------------ #
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
                    parsed = _parse_list_line(line)
                    if not parsed:
                        continue
                    flags, _delim, raw_name = parsed
                    if "\\noselect" in flags:
                        continue
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
        """Reads message metadata (headers only, read-only). Raises on connection problems."""
        profile = self._get_profile(account_id)
        if not profile:
            raise RuntimeError("IMAP-Profil nicht gefunden")

        date_from = ensure_utc(date_from) if date_from else None
        date_to = ensure_utc(date_to) if date_to else None

        try:
            client = self._connect(profile)
        except (imaplib.IMAP4.error, OSError) as ex:
            raise RuntimeError(f"IMAP-Anmeldung an '{profile.host}' fehlgeschlagen: {ex}") from ex

        emails: List[EmailItem] = []
        try:
            for folder in folder_paths:
                if max_count and len(emails) >= max_count:
                    break
                status, _ = client.select(_quote(folder), readonly=True)
                if status != "OK":
                    logger.warning("Could not select IMAP folder %r", folder)
                    continue
                uidvalidity = self._read_uidvalidity(client) or "0"

                # Narrow down on the server (with a safety margin, because the server
                # filters by arrival date); the exact filter is applied below.
                criteria: List[str] = []
                if date_from:
                    criteria += ["SINCE", _imap_date(date_from - timedelta(days=2))]
                if date_to:
                    criteria += ["BEFORE", _imap_date(date_to + timedelta(days=3))]
                status, data = client.uid("SEARCH", None, *(criteria or ["ALL"]))
                if status != "OK" or not data or not data[0]:
                    continue

                uids = [u.decode() for u in reversed(data[0].split())]  # newest first
                total = len(uids)

                for start in range(0, total, FETCH_CHUNK_SIZE):
                    if max_count and len(emails) >= max_count:
                        break
                    chunk = uids[start:start + FETCH_CHUNK_SIZE]
                    res, msg_data = client.uid(
                        "FETCH", ",".join(chunk),
                        "(UID RFC822.SIZE INTERNALDATE FLAGS BODY.PEEK[HEADER])",
                    )
                    if res != "OK" or not msg_data:
                        continue

                    records = sorted(
                        self._iter_fetch_records(msg_data),
                        key=lambda rec: int(rec[0]),
                        reverse=True,
                    )
                    for uid, meta_info, raw_header in records:
                        if max_count and len(emails) >= max_count:
                            break
                        item = self._build_email_item(
                            profile, account_id, folder, uidvalidity, uid, meta_info, raw_header
                        )
                        if date_from and item.received_time < date_from:
                            continue
                        if date_to and item.received_time > date_to:
                            continue
                        emails.append(item)
                        if progress_callback:
                            progress_callback(len(emails), total)
        except (imaplib.IMAP4.error, OSError) as ex:
            raise RuntimeError(f"IMAP-Fehler beim Abrufen der E-Mails: {ex}") from ex
        finally:
            try:
                client.logout()
            except Exception:
                pass

        return emails

    @staticmethod
    def _iter_fetch_records(msg_data: List[Any]) -> Iterator[Tuple[str, bytes, bytes]]:
        """Yields (uid, meta, raw header) for each message of a FETCH response."""
        records: List[List[bytes]] = []
        current: Optional[List[bytes]] = None
        for part in msg_data:
            if isinstance(part, tuple) and len(part) >= 2:
                current = [part[0] or b"", part[1] or b""]
                records.append(current)
            elif isinstance(part, bytes) and current is not None:
                if re.match(rb"\s*\d+ \(", part):
                    # Unrelated untagged FETCH (e.g. a flag update for another message)
                    current = None
                else:
                    # Attributes the server sent after the header literal
                    current[0] += b" " + part
        for meta, raw_header in records:
            match = re.search(rb"\bUID (\d+)", meta)
            if match:
                yield match.group(1).decode(), meta, raw_header

    def _build_email_item(
        self,
        profile: ImapConfig,
        account_id: str,
        folder: str,
        uidvalidity: str,
        uid: str,
        meta_info: bytes,
        raw_header: bytes,
    ) -> EmailItem:
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

        headers_dict = {}
        for h_key in msg.keys():
            headers_dict[h_key] = str(msg.get(h_key, ""))

        return EmailItem(
            id=f"{account_id}_{folder}_{uidvalidity}-{uid}",
            entry_id=uid,
            store_id=account_id,
            account_name=profile.account_name,
            subject=subject,
            sender_name=decoded_sender_name,
            sender_email=decoded_sender_email,
            received_time=received_time,
            body_preview=subject,
            is_read=b"\\Seen" in meta_info,
            folder_path=decode_imap_utf7(folder),
            size_bytes=size_bytes,
            headers=headers_dict,
        )

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
        new_uid: Optional[str] = None
        new_folder: Optional[str] = None
        try:
            session = self._get_session(account_id)
            folder, uidvalidity, uid = self._parse_email_id(action.email_id, account_id)

            self._select(session, folder, readonly=False)
            if uidvalidity != "0" and session.uidvalidity and session.uidvalidity != uidvalidity:
                raise ImapActionError(
                    "Der Ordner wurde seit dem Scan auf dem Server neu aufgebaut. Bitte Postfach neu scannen."
                )
            # Also guarantees that the UID still refers to an existing message.
            message_id = self._fetch_message_id(session, uid)

            # Resolve (and if necessary create) the target folder first, so that a
            # missing folder fails the action before anything has been changed.
            raw_target: Optional[str] = None
            if action.target_folder:
                raw_target = self._resolve_target_folder(session, action.target_folder)

            changes: List[str] = []
            if action.mark_as_read:
                self._uid_store(session, uid, "+FLAGS", "(\\Seen)")
                changes.append("Als gelesen markiert")
            elif action.mark_as_unread:
                self._uid_store(session, uid, "-FLAGS", "(\\Seen)")
                changes.append("Als ungelesen markiert")

            if raw_target and raw_target != folder:
                new_uid = self._move(session, uid, raw_target, message_id)
                new_folder = raw_target
                changes.append(f"Verschoben nach '{decode_imap_utf7(raw_target)}'")

            return ExecutionResult(
                action=action,
                success=True,
                message=", ".join(changes) if changes else "Keine Änderungen nötig",
                new_entry_id=new_uid,
                new_folder=new_folder,
            )
        except ImapActionError as ex:
            return ExecutionResult(action=action, success=False, message=f"IMAP: {ex}")
        except (imaplib.IMAP4.abort, OSError) as ex:
            self._drop_session()
            return ExecutionResult(action=action, success=False, message=f"IMAP-Verbindung unterbrochen: {ex}")
        except Exception as ex:
            if self._session is not None:
                self._session.selected = None
            return ExecutionResult(action=action, success=False, message=f"IMAP-Fehler: {ex}")

    def restore_item(
        self,
        entry_id: str,
        store_id: str,
        target_folder: str,
        is_read: bool,
        categories: List[str],
        current_folder: Optional[str] = None,
    ) -> Optional[str]:
        """Moves a message back to its original folder and restores its read state.

        ``target_folder`` is the original folder as shown to the user (decoded),
        ``current_folder`` the raw folder the message was moved to and ``entry_id``
        its UID there. Raises if the message cannot be restored.
        """
        try:
            session = self._get_session(store_id)
            raw_original = encode_imap_utf7(target_folder)
            uid: Optional[str] = entry_id
            moved_back = False

            if current_folder and current_folder != raw_original:
                if not uid:
                    raise ImapActionError(
                        f"Neue Position in '{decode_imap_utf7(current_folder)}' unbekannt – bitte manuell zurückverschieben"
                    )
                self._select(session, current_folder, readonly=False)
                message_id = self._fetch_message_id(session, uid)
                self._ensure_folder(session, raw_original)
                uid = self._move(session, uid, raw_original, message_id)
                moved_back = True
            elif not uid:
                raise ImapActionError("UID der E-Mail unbekannt")

            if uid is None:
                # Moved back, but the server did not tell us the new UID.
                logger.warning("Restored message to %r but could not reset its read state", target_folder)
                return None

            self._select(session, raw_original, readonly=False)
            if not moved_back:
                self._fetch_message_id(session, uid)
            self._uid_store(session, uid, "+FLAGS" if is_read else "-FLAGS", "(\\Seen)")
            return uid if moved_back else None
        except (imaplib.IMAP4.abort, OSError):
            self._drop_session()
            raise
        except imaplib.IMAP4.error:
            if self._session is not None:
                self._session.selected = None
            raise
