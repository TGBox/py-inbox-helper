"""Minimal in-memory IMAP4rev1 server for tests.

It speaks just enough of the protocol for ImapMailProvider, so the tests run
against the real ``imaplib`` client instead of mocks.
"""
from __future__ import annotations

import re
import socket
import threading
from typing import Dict, List, Optional, Set


class FakeImapServer:
    def __init__(self, capabilities=("IMAP4rev1", "UIDPLUS", "MOVE", "NAMESPACE"), delimiter: str = "/"):
        self.capabilities = list(capabilities)
        self.delimiter = delimiter
        self.password = "secret"
        self.reject_copy = False
        self.mailboxes: Dict[str, Dict[int, dict]] = {}
        self.list_flags: Dict[str, str] = {}
        self.next_uid: Dict[str, int] = {}
        self.uidvalidity: Dict[str, int] = {}
        self.commands: List[str] = []
        self.add_mailbox("INBOX")
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    # ---- test setup / inspection helpers ----
    def add_mailbox(self, name: str, flags: str = "\\HasNoChildren") -> None:
        self.mailboxes[name] = {}
        self.list_flags[name] = flags
        self.next_uid[name] = 1
        self.uidvalidity[name] = 1000 + len(self.mailboxes)

    def add_message(self, mailbox: str, headers: bytes, flags=(), size: int = 1000,
                    internaldate: str = "15-May-2024 14:30:00 +0200") -> int:
        uid = self.next_uid[mailbox]
        self.next_uid[mailbox] += 1
        self.mailboxes[mailbox][uid] = {
            "headers": headers, "flags": set(flags), "size": size, "internaldate": internaldate,
        }
        return uid

    def subjects(self, mailbox: str) -> List[str]:
        result = []
        for uid in sorted(self.mailboxes[mailbox]):
            match = re.search(rb"^Subject: (.*)\r$", self.mailboxes[mailbox][uid]["headers"], re.M)
            result.append(match.group(1).decode() if match else "")
        return result

    def stop(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    # ---- protocol ----
    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        rfile = conn.makefile("rb")
        selected: Optional[str] = None

        def send(text: str) -> None:
            conn.sendall(text.encode("utf-8") + b"\r\n")

        def seq(uid: int) -> int:
            return sorted(self.mailboxes[selected]).index(uid) + 1

        send("* OK fake IMAP ready")
        try:
            while True:
                raw = rfile.readline()
                if not raw:
                    return
                line = raw.decode("utf-8").rstrip("\r\n")
                self.commands.append(line.split(" ", 1)[1] if " " in line else line)
                tag, _, rest = line.partition(" ")
                cmd, _, args = rest.partition(" ")
                cmd = cmd.upper()
                if cmd == "UID":
                    sub, _, args = args.partition(" ")
                    cmd = "UID " + sub.upper()

                if cmd == "CAPABILITY":
                    send("* CAPABILITY " + " ".join(self.capabilities))
                    send(f"{tag} OK done")
                elif cmd == "LOGIN":
                    if self._unquote(args.split(" ", 1)[1]) == self.password:
                        send(f"{tag} OK logged in")
                    else:
                        send(f"{tag} NO [AUTHENTICATIONFAILED] invalid credentials")
                elif cmd == "NAMESPACE":
                    send(f'* NAMESPACE (("" "{self.delimiter}")) NIL NIL')
                    send(f"{tag} OK done")
                elif cmd == "LIST":
                    for name, flags in self.list_flags.items():
                        send(f'* LIST ({flags}) "{self.delimiter}" "{name}"')
                    send(f"{tag} OK done")
                elif cmd in ("SELECT", "EXAMINE"):
                    name = self._unquote(args)
                    if name not in self.mailboxes:
                        selected = None
                        send(f"{tag} NO no such mailbox")
                        continue
                    selected = name
                    send(f"* {len(self.mailboxes[name])} EXISTS")
                    send(f"* OK [UIDVALIDITY {self.uidvalidity[name]}] UIDs valid")
                    send(f"{tag} OK [READ-WRITE] done")
                elif cmd == "CREATE":
                    name = self._unquote(args)
                    if name in self.mailboxes:
                        send(f"{tag} NO mailbox exists")
                    else:
                        self.add_mailbox(name)
                        send(f"{tag} OK created")
                elif cmd == "SUBSCRIBE":
                    send(f"{tag} OK done")
                elif cmd == "UID SEARCH":
                    uids = sorted(self.mailboxes[selected])
                    match = re.search(r'HEADER Message-ID "((?:[^"\\]|\\.)*)"', args)
                    if match:
                        needle = match.group(1).encode()
                        uids = [u for u in uids if needle in self.mailboxes[selected][u]["headers"]]
                    send("* SEARCH " + " ".join(str(u) for u in uids))
                    send(f"{tag} OK done")
                elif cmd == "UID FETCH":
                    uid_set, _, items = args.partition(" ")
                    for uid in self._uids(uid_set, selected):
                        msg = self.mailboxes[selected][uid]
                        if "HEADER.FIELDS" in items:
                            match = re.search(rb"^Message-ID: .*\r\n", msg["headers"], re.M | re.I)
                            body = (match.group(0) if match else b"") + b"\r\n"
                            conn.sendall(
                                f"* {seq(uid)} FETCH (UID {uid} BODY[HEADER.FIELDS (MESSAGE-ID)] {{{len(body)}}}\r\n".encode()
                                + body + b")\r\n"
                            )
                        else:
                            flags = " ".join(sorted(msg["flags"]))
                            # FLAGS deliberately sent AFTER the literal, as some servers do
                            conn.sendall(
                                f'* {seq(uid)} FETCH (UID {uid} RFC822.SIZE {msg["size"]} '
                                f'INTERNALDATE "{msg["internaldate"]}" BODY[HEADER] {{{len(msg["headers"])}}}\r\n'.encode()
                                + msg["headers"] + f" FLAGS ({flags}))\r\n".encode()
                            )
                    send(f"{tag} OK done")
                elif cmd == "UID STORE":
                    uid_set, op, flag_str = args.split(" ", 2)
                    flags = set(flag_str.strip("()").split())
                    for uid in self._uids(uid_set, selected):
                        msg = self.mailboxes[selected][uid]
                        msg["flags"] = msg["flags"] | flags if op.startswith("+") else msg["flags"] - flags
                        send(f'* {seq(uid)} FETCH (UID {uid} FLAGS ({" ".join(sorted(msg["flags"]))}))')
                    send(f"{tag} OK done")
                elif cmd in ("UID COPY", "UID MOVE"):
                    uid_set, _, target = args.partition(" ")
                    target = self._unquote(target)
                    if self.reject_copy or target not in self.mailboxes:
                        send(f"{tag} NO [TRYCREATE] cannot copy")
                        continue
                    pairs = []
                    for uid in self._uids(uid_set, selected):
                        msg = self.mailboxes[selected][uid]
                        new_uid = self.add_message(target, msg["headers"], msg["flags"], msg["size"], msg["internaldate"])
                        pairs.append((uid, new_uid))
                    code = ""
                    if "UIDPLUS" in self.capabilities and pairs:
                        code = (f"[COPYUID {self.uidvalidity[target]} "
                                f"{','.join(str(a) for a, _ in pairs)} {','.join(str(b) for _, b in pairs)}] ")
                    if cmd == "UID MOVE":
                        if code:
                            send(f"* OK {code}moved")
                        for uid, _ in pairs:
                            send(f"* {seq(uid)} EXPUNGE")
                            del self.mailboxes[selected][uid]
                        send(f"{tag} OK done")
                    else:
                        send(f"{tag} OK {code}done")
                elif cmd in ("UID EXPUNGE", "EXPUNGE"):
                    only = set(self._uids(args, selected)) if cmd == "UID EXPUNGE" else None
                    for uid in sorted(self.mailboxes[selected]):
                        if "\\Deleted" in self.mailboxes[selected][uid]["flags"] and (only is None or uid in only):
                            send(f"* {seq(uid)} EXPUNGE")
                            del self.mailboxes[selected][uid]
                    send(f"{tag} OK done")
                elif cmd == "LOGOUT":
                    send("* BYE bye")
                    send(f"{tag} OK done")
                    return
                else:
                    send(f"{tag} BAD unknown command {cmd}")
        except (OSError, ValueError):
            return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    @staticmethod
    def _unquote(value: str) -> str:
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return value

    def _uids(self, uid_set: str, mailbox: str) -> List[int]:
        wanted: Set[int] = set()
        for part in uid_set.split(","):
            if ":" in part:
                low, high = part.split(":")
                wanted.update(range(int(low), int(high) + 1))
            else:
                wanted.add(int(part))
        return [u for u in sorted(self.mailboxes[mailbox]) if u in wanted]
