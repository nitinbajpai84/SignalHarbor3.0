"""File connectors (W1): they only fetch; the readers of v3_pack_readers_feeds read what they drop (see base.py).

  sftp_folder   a folder that stands in for an SFTP mount (env SH_FEED_SFTP_DIR): every file changed since the date
  imap_inbox    a mailbox over IMAP (env SH_FEED_IMAP_HOST, SH_FEED_IMAP_USER, SH_FEED_IMAP_PASSWORD): each mail as .eml, and its attachments as files
  mt940, camt053, mt535_536, bai2   the same folder, only the files of that format (by name pattern, then confirmed by content)

A key is read from its environment variable only, and never written into a receipt or a message. The mailbox is the customer's own, named in the settings; the
client is injectable (`ImapInbox(client_factory=...)`) so a test uses a fake and never opens a socket."""
from __future__ import annotations

import email
import fnmatch
import hashlib
import imaplib
import os
import re
from datetime import date, datetime
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path

from sh_platform.v1.connectors.base import Fetched, register

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DATED = re.compile(r"20\d{2}-?\d{2}-?\d{2}")


def dated(name: str, day: date) -> str:
    """The file lands under a dated name, so folder_month puts it in the month it arrived."""
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", Path(name).name).strip() or "file"
    return name if DATED.search(name) else f"{day.isoformat()}_{name}"


class SftpFolder:
    id, label, kind, env = "sftp_folder", "SFTP drop (custodian files)", "sftp", ("SH_FEED_SFTP_DIR",)
    patterns: tuple[str, ...] = ("*",)
    kinds: tuple[str, ...] = ()  # when set, a file must also be read as one of these by the pack's kind_of

    def fetch(self, since: date) -> list[Fetched]:
        root = Path(os.environ[self.env[0]])
        out = []
        for p in sorted(root.iterdir()):
            if not p.is_file() or not any(fnmatch.fnmatch(p.name.lower(), pat) for pat in self.patterns):
                continue
            day = datetime.fromtimestamp(p.stat().st_mtime).date()
            if day < since:
                continue
            data = p.read_bytes()
            if self.kinds:
                from sh_platform.v1 import v3_pack_readers as PK
                if (PK.kind_of(p.name, data) or ("",))[0] not in self.kinds:
                    continue
            out.append(Fetched(dated(p.name, day), data, f"SFTP folder, file {p.name}"))
        return out


class FormatFeed(SftpFolder):
    def __init__(self, id: str, label: str, patterns: tuple[str, ...], kinds: tuple[str, ...]):
        self.id, self.label, self.kind, self.patterns, self.kinds = id, label, "file format", patterns, kinds


class ImapInbox:
    id, label, kind = "imap_inbox", "Email inbox (IMAP)", "inbox"
    env = ("SH_FEED_IMAP_HOST", "SH_FEED_IMAP_USER", "SH_FEED_IMAP_PASSWORD")

    def __init__(self, client_factory=None, folder: str = "INBOX"):
        self.factory, self.folder = client_factory or imaplib.IMAP4_SSL, folder

    def fetch(self, since: date) -> list[Fetched]:
        host, user, password = (os.environ[n] for n in self.env)
        c = self.factory(host)
        out: list[Fetched] = []
        try:
            c.login(user, password)
            c.select(self.folder, readonly=True)
            _, found = c.search(None, "SINCE", f"{since.day:02d}-{MONTHS[since.month - 1]}-{since.year}")
            for num in (found[0] or b"").split():
                _, got = c.fetch(num, "(RFC822)")
                raw = got[0][1]
                msg = email.message_from_bytes(raw, policy=policy.default)
                try:
                    day = parsedate_to_datetime(msg["Date"]).date()
                except (TypeError, ValueError):
                    day = since
                src = f"IMAP inbox {user}, mail '{str(msg['Subject'] or '')[:60]}' of {day.isoformat()}"
                tag = hashlib.sha1(str(msg["Message-ID"] or raw[:200]).encode()).hexdigest()[:8]
                subject = re.sub(r"[^A-Za-z0-9]+", "-", str(msg["Subject"] or "mail"))[:40].strip("-")
                out.append(Fetched(f"{day.isoformat()}_{tag}_{subject}.eml", raw, src))
                for part in msg.iter_attachments():
                    if (name := part.get_filename()) and (body := part.get_content()):
                        out.append(Fetched(dated(name, day), body if isinstance(body, bytes) else str(body).encode("utf-8"), src + f", attachment {name}"))
        finally:
            try:
                c.logout()
            except Exception:  # noqa: BLE001 - a mailbox that will not say goodbye has still given its mail
                pass
        return out


for _c in (SftpFolder(), ImapInbox(),
           FormatFeed("mt940", "SWIFT MT940 bank statements", ("*.sta", "*.mt940", "*.940", "*.txt", "*.swift"), ("swift_mt940",)),
           FormatFeed("camt053", "ISO 20022 camt.053 bank statements", ("*.xml", "*.camt", "*camt*"), ("iso_camt053",)),
           FormatFeed("mt535_536", "SWIFT MT535 holdings and MT536 transactions", ("*.txt", "*.mt535", "*.mt536", "*.535", "*.536", "*.swift"), ("swift_mt535", "swift_mt536")),
           FormatFeed("bai2", "BAI2 bank statements", ("*.bai", "*.bai2", "*.txt", "*.csv"), ("bai2",))):
    register(_c)
