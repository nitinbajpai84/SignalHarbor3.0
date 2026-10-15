"""Guard 3: the name vault. Swaps names for stable tokens (PERSON_001) and back, inside the plane.

The vault file (`name_vault.json` in the company's context area) holds real names, so it never
leaves the plane and is never logged.

Safety rules of the file
- A MISSING file is an empty vault. A file that cannot be read, is corrupt or is locked too long
  raises `VaultUnavailable` (the gateway then refuses with `vault_unavailable`). The vault never
  overwrites or truncates a file it could not read.
- The file is re-read on every use, so two NameVault objects on one plane stay consistent. Only
  `register` writes: it locks, re-reads, merges its name into what is on disk, saves, unlocks.
  Matching (tokenise, contains_name) never holds the lock: the lock is held only to load or to
  merge-and-save, which takes milliseconds.
- The lock file records the owner (process id, a unique token and the time). A lock is broken, with a
  logged warning, when its file is empty (an owner killed before it wrote; after a 2 second grace),
  when its owner process is gone, or when it is older than _LOCK_STALE (60 s; the lock is held for
  milliseconds). A lock file with any other content that cannot be read as an owner (malformed pid
  or time) is broken only after the hard limit of 10 minutes, which also breaks any lock. The
  owner removes the lock only if the file still carries its own token. Break-and-recreate has a tiny race window that is
  documented here rather than closed (no OS file-lock calls, to stay portable).
- At most MAX_ENTRIES (20 000) registered names; a bigger vault is refused at register.
- Only names that are registered are stored. E-mails, phone numbers and long digit strings found
  by pattern get tokens that live in memory in this object only (up to 10 000, oldest dropped), so
  a reply in the same process can be mapped back; they are not written to the vault file.

How names are matched ("folding"): text and names are normalised the same way before matching:
NFKD, accents and combining marks dropped, zero-width and soft-hyphen characters dropped,
upper/lower case ignored, any run of white space or control characters (tab, newline, vertical
tab ...) read as one space, a letter-by-letter hyphen plus line break ignored, and a small table
of Cyrillic/Greek look-alikes mapped to Latin (a e o p c x y i s h k m t and a few more). So
"Zoe Muller" matches "Zoë Müller", "Nоrthwind" with a Cyrillic o matches "Northwind", and
"North-<newline>wind Traders" matches "Northwind Traders". Names are matched with one compiled
pattern (a letter tree) per vault state, so a 3000-name vault takes well under a second per call.
Still NOT covered: look-alikes outside that table, other scripts (Arabic, CJK, Hebrew) written
with different characters, nicknames, misspellings, initials, a name spelled with letters spread
over several words, and a name written inside an image or encoded text (base64).

What the patterns catch, and where they fail (guesses, not proof):
- E-mail addresses: name@host.tld and "name at host dot tld". Other spellings are missed; a
  sentence shaped like "meet at noon dot com" is a false positive.
- Phone numbers: international (+ then 8+ digits, spaces/dashes allowed) and local 3-part forms
  such as 6123 4567 x or 012-345-6789. Short or oddly spaced numbers are missed.
- Account or policy numbers: any run of 8 or more digits. FALSE NEGATIVES: shorter account
  numbers, ids with letters mixed in, and digits split by spaces. FALSE POSITIVES: any 8+ digit
  figure written without separators inside text.
`contains_name` is the stricter second look the gateway runs on the outgoing strings and final
body: it also finds a registered name whose parts are joined across a hyphen or a line break
("Et-<newline>han", "Daniel-Kerr", "DanielKerr"), as a word of its own (digits may touch it). It never
joins across ordinary spaces, so "more than a third" does not contain "Ethan". Names under 4 letters
are matched as whole words only.
"""
import ctypes
import json
import logging
import os
import re
import threading
import time
import unicodedata
import uuid
from contextlib import contextmanager

from sh_platform.egress.names import is_everyday_word
from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import CompanyPlane

KINDS = ("company", "person", "fund", "account", "portfolio", "counterparty", "policy_number")
MAX_ENTRIES = 20_000
MAX_NAME_CHARS = 200
_SESSION_CAP = 10_000
_PREFIX = {k: k.upper() for k in KINDS} | {"email": "EMAIL", "phone": "PHONE", "number": "NUMBER"}
_NUMBER = re.compile(r"(?<![\w.])\d{8,}(?![\w])")
_PATTERNS = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("email", re.compile(r"[\w.+-]+\s+at\s+[\w-]+(?:\s+dot\s+[\w-]+)+", re.I)),
    ("phone", re.compile(r"\+\d[\d\s().-]{7,}\d")),
    ("phone", re.compile(r"(?<![\w.])\(?\d{2,4}\)?[\s.-]\d{3,4}[\s.-]\d{3,4}(?![\w.])")),
    ("number", _NUMBER),
)
_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Z_]+_\d{3,}(?![A-Za-z0-9_])")
_LOOSE_TOKEN = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z_]*[ \u00a0-]\d{3,}(?![A-Za-z0-9_])")  # the same token with a space or hyphen
_LOCK_WAIT = 5.0
_THREADS: dict[str, threading.Lock] = {}  # one per vault file: threads of this process queue here, so the lock-file wait is only for other processes
_THREADS_GUARD = threading.Lock()
_LOCK_STALE = 60.0   # a well-formed lock this old is broken whatever its owner (held for milliseconds)
_LOCK_EMPTY_GRACE = 2.0  # an empty lock file this old is broken (its owner died before writing)
_LOCK_HARD = 600.0   # a lock this old is broken whatever its content
_log = logging.getLogger(__name__)
_JOIN = re.compile(r" *(?:- *(?:\r\n|[\r\n\t\v\f])?|\r\n|[\r\n\t\v\f]) *")  # a hyphen and/or line break (or tab)
# Cyrillic and Greek look-alikes (lower case, applied after case folding) -> Latin
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "і": "i", "ѕ": "s",
    "һ": "h", "к": "k", "м": "m", "т": "t", "ј": "j", "ԁ": "d", "ԛ": "q", "ԝ": "w",
    "α": "a", "ε": "e", "ο": "o", "ρ": "p", "ν": "v", "ι": "i", "κ": "k", "τ": "t", "υ": "u",
    "χ": "x", "η": "n", "μ": "m", "β": "b", "γ": "y",
    "ı": "i", "ø": "o", "đ": "d", "ł": "l",
})
_ASCII_FOLD = {i: " " for i in range(128) if chr(i).isspace() or unicodedata.category(chr(i))[0] == "C"}
_ASCII_FOLD |= {i: chr(i + 32) for i in range(65, 91)}


_ESCAPED_SPACE = re.compile(r"(?<!\\)\\[nrt]")  # a JSON line break or tab escape, not an escaped backslash


def tokens_in(text: str) -> set:
    return set(_TOKEN.findall(text))


class VaultUnavailable(Exception):
    """The vault file could not be read, locked or saved. Nothing may leave until it is fixed."""


def _fold_map(text: str):
    """Folded text plus, for each folded character, the index of the original character."""
    if text.isascii():
        return text.translate(_ASCII_FOLD), range(len(text))
    out, idx = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKD", ch):
            cat = unicodedata.category(c)
            if cat in ("Mn", "Me", "Cf"):
                continue
            for cc in c.casefold().translate(_CONFUSABLES):
                out.append(" " if (cat[0] in "CZ" or cc.isspace()) else cc)
                idx.append(i)
    return "".join(out), idx


def _fold(text: str) -> str:
    return " ".join(_fold_map(text)[0].split())


def _compact(text: str) -> str:
    return re.sub(r"[\W_]+", "", text)


class _Node:
    __slots__ = ("kids", "end")

    def __init__(self):
        self.kids: dict[str, "_Node"] = {}
        self.end = False


def _trie_regex(paths: list[list[str]]) -> re.Pattern | None:
    """One pattern for many names: a letter tree, longest name first, path-compressed so the
    nesting stays shallow. Each path is a list of regex pieces."""
    if not paths:
        return None
    root = _Node()
    for p in paths:
        n = root
        for label in p:
            n = n.kids.setdefault(label, _Node())
        n.end = True

    def emit(node: _Node) -> str:
        parts = []
        for label, child in node.kids.items():
            seq = [label]
            while len(child.kids) == 1 and not child.end:
                (lab, child), = child.kids.items()
                seq.append(lab)
            sub = ""
            if child.kids:
                sub = "(?:" + emit(child) + ("|)" if child.end else ")")
            parts.append("".join(seq) + sub)
        return "|".join(parts)
    return re.compile("(?:" + emit(root) + ")")


def _name_paths(folded: str) -> list[str]:
    """Regex pieces for a folded name: words apart by any punctuation, letters allowed to be
    split by a hyphen plus line break."""
    out = []
    for wi, word in enumerate(folded.split()):
        if wi:
            out.append(r"[\W_]+")
        for ci, c in enumerate(word):
            out.append((r"(?:-\s+)?" if ci else "") + re.escape(c))
    return out


def _generic(name: str) -> bool:
    """A single everyday word ("portfolio", "September", "Entity"): never matched as a name (ER-01)."""
    words = str(name or "").split()
    return len(words) == 1 and is_everyday_word(words[0])


class _State:
    """Everything derived from one version of the file (cached until the file text changes)."""

    def __init__(self, raw, entries: dict, own: str = ""):
        self.raw, self.entries = raw, entries
        self.by_compact: dict[str, str] = {}
        paths, glue = [], []
        for tok, e in entries.items():
            f = _fold(e["name"])
            c = _compact(f)
            if not c or _generic(e["name"]) or c == own:  # TAQ-S1: never the company's own id word; AQ1: a vault poisoned by an older build heals on read; the token still maps back
                continue
            if c not in self.by_compact:
                self.by_compact[c] = tok
                paths.append(_name_paths(f))
                if len(c) >= 4:  # each word's letters together, any or no separator between words
                    glue.append([p for i, w in enumerate(f.split()) for p in ([r"[\W_]*"] if i else []) +
                                 [re.escape(ch) for ch in _compact(w)]])
        self.whole = _trie_regex(paths)
        self.glue = _trie_regex(glue)
        if self.glue is not None:  # a word of its own: no letter or underscore may touch it (digits may). AQ1 (ER-01): an underscore
            # joins the parts of an identifier ("portfolio_id", "gold_investment_report_cash_daily"), exactly as tokenise reads it, so the
            # final check never refuses a call for a glued form tokenise left alone.
            self.glue = re.compile(r"(?<![^\W\d])" + self.glue.pattern + r"(?![^\W\d])")
        self.whole_wb = (re.compile(r"(?<!\w)" + self.whole.pattern + r"(?!\w)")
                         if self.whole is not None else None)


class NameVault:
    def __init__(self, plane: CompanyPlane):
        self.plane = plane
        self._path = plane.area("context") / "name_vault.json"
        self._lock = self._path.with_name(self._path.name + ".lock")
        self._st: _State | None = None
        # TAQ-S1: the company's own id word ("evergreen") is in every path and identifier: kept if registered, never matched as a name
        self._own = _compact(_fold(str(getattr(plane, "company_id", "") or "")))
        self._session: dict[str, str] = {}      # token -> value (pattern-found, memory only)
        self._session_rev: dict[tuple, str] = {}

    # -- lock
    @staticmethod
    def _pid_alive(pid) -> bool:
        if not isinstance(pid, int) or pid <= 0:
            return False
        if os.name == "nt":
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return k.GetLastError() == 5  # access denied: it exists
            try:
                code = ctypes.c_ulong()
                return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
            finally:
                k.CloseHandle(h)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _read_lock(self):
        try:
            return json.loads(self._lock.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _break_if_dead(self) -> None:
        """Break the lock (logged) if its file is empty past a short grace, or it names an owner process
        that is gone, or it is older than _LOCK_STALE; a malformed lock only past the hard limit."""
        try:
            age = file_age = time.time() - self._lock.stat().st_mtime
            raw = self._lock.read_bytes()  # one read per look: every open delays the owner's unlink on Windows
        except OSError:
            return
        empty = not raw.strip()
        try:
            info = json.loads(raw)
        except ValueError:
            info = None
        reason = None
        if empty:
            reason = "empty" if age >= _LOCK_EMPTY_GRACE else None
        elif (isinstance(info, dict) and isinstance(info.get("pid"), int)
              and isinstance(info.get("t"), (int, float)) and not isinstance(info.get("t"), bool)):
            age = time.time() - info["t"]
            if age >= _LOCK_STALE:
                reason = "older than %ds" % _LOCK_STALE
            elif info["pid"] != os.getpid() and not self._pid_alive(info["pid"]):  # own pid: alive, no system call
                reason = "owner process gone"
        if reason is None and max(age, file_age) >= _LOCK_HARD:  # unreadable or malformed owner: only the hard limit
            reason = "older than the hard limit"
        if reason and self._read_lock() == info:  # still the same lock we looked at
            try:
                self._lock.unlink()
                _log.warning("name vault: broke a stale lock (%s): %s", reason, self._lock.name)
            except OSError:
                pass

    def _release(self, token: str) -> None:
        # Up to 2 s: on Windows every waiter's look at the lock file blocks the unlink for a moment; with many
        # waiters 20 tries (0.2 s) could all collide and leave a live lock behind, refusing every call.
        for _ in range(200):
            info = self._read_lock()
            if not isinstance(info, dict) or info.get("token") != token:
                return  # not ours any more (or already gone): never remove someone else's lock
            try:
                self._lock.unlink()
                return
            except FileNotFoundError:
                return
            except OSError:
                time.sleep(0.01)
        _log.warning("name vault: could not remove its own lock: %s", self._lock.name)

    # ponytail: O_EXCL lock file, not an OS file lock; break-and-recreate has a tiny race (see the header). Ceiling:
    # many writer processes on one vault; then use msvcrt.locking / fcntl.flock.
    @contextmanager
    def _locked(self):
        with _THREADS_GUARD:
            mine = _THREADS.setdefault(str(self._lock), threading.Lock())
        if not mine.acquire(timeout=_LOCK_WAIT):
            raise VaultUnavailable
        try:
            with self._file_locked():
                yield
        finally:
            mine.release()

    @contextmanager
    def _file_locked(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise VaultUnavailable from None
        token = uuid.uuid4().hex
        start = time.monotonic()
        while True:
            try:
                fd = os.open(self._lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except (FileExistsError, PermissionError):  # Windows: PermissionError while it is being deleted
                self._break_if_dead()
                if time.monotonic() - start > _LOCK_WAIT:
                    raise VaultUnavailable from None
                time.sleep(0.005)
                continue
            except OSError:
                raise VaultUnavailable from None
            try:
                os.write(fd, json.dumps({"pid": os.getpid(), "token": token, "t": time.time()}).encode())
            finally:
                os.close(fd)
            break
        try:
            yield
        finally:
            self._release(token)

    # -- file
    def _read_raw(self):
        """The file text, or None if it does not exist. Call under the lock."""
        try:
            return self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            raise VaultUnavailable from None

    @staticmethod
    def _parse(raw) -> dict:
        if raw is None:
            return {}  # never created: an empty vault
        try:
            entries = json.loads(raw)["entries"]
            ok = isinstance(entries, dict) and all(
                isinstance(t, str) and isinstance(e, dict) and e.get("kind") in _PREFIX
                and isinstance(e.get("name"), str) for t, e in entries.items())
        except (ValueError, KeyError, TypeError, RecursionError):
            ok = False
        if not ok:
            raise VaultUnavailable  # unreadable or corrupt: never replaced from memory
        return entries

    def _save(self, entries: dict) -> None:
        for attempt in range(20):
            try:
                write_json_atomic(self._path, {"entries": entries})
                return
            except PermissionError:  # Windows: a reader has the file for a moment
                time.sleep(0.01)
            except OSError:
                break
        raise VaultUnavailable

    def _state(self) -> _State:
        with self._locked():
            raw = self._read_raw()
        if self._st is not None and self._st.raw == raw:
            return self._st
        self._st = _State(raw, self._parse(raw), self._own)
        return self._st

    # -- register (the only writer)
    def register(self, kind: str, name: str) -> str:
        if kind not in KINDS:
            raise ValueError("unknown kind")
        if not isinstance(name, str) or not _compact(_fold(name)):
            raise ValueError("empty name")
        if len(name) > MAX_NAME_CHARS:
            raise ValueError("name too long")
        name = name.strip()
        if _generic(name):
            raise ValueError("generic word")  # AQ1 (ER-01): a single everyday word is never a name
        with self._locked():
            entries = self._parse(self._read_raw())
            key = name.casefold()
            for tok, e in entries.items():
                if e["kind"] == kind and e["name"].casefold() == key:
                    return tok
            if len(entries) >= MAX_ENTRIES:
                raise ValueError("vault is full")
            prefix = _PREFIX[kind]
            top = max((int(t.rsplit("_", 1)[1]) for t in entries
                       if t.rsplit("_", 1)[0] == prefix and t.rsplit("_", 1)[1].isdigit()), default=0)
            tok = f"{prefix}_{top + 1:03d}"
            entries[tok] = {"kind": kind, "name": name}
            self._save(entries)
            return tok

    def _session_token(self, kind: str, value: str) -> str:
        key = (kind, value.casefold())
        tok = self._session_rev.get(key)
        if tok:
            return tok
        if len(self._session) >= _SESSION_CAP:
            old = next(iter(self._session))
            v = self._session.pop(old)
            self._session_rev.pop((old.rsplit("_", 1)[0].lower(), v.casefold()), None)
        n = sum(1 for t in self._session if t.startswith(_PREFIX[kind] + "_")) + 1
        tok = f"{_PREFIX[kind]}_{n:03d}"
        while tok in self._session:
            n += 1
            tok = f"{_PREFIX[kind]}_{n:03d}"
        self._session[tok] = value
        self._session_rev[key] = tok
        return tok

    def known_tokens(self) -> set:
        """Tokens that exist now: registered ones and this object's pattern tokens."""
        return set(self._state().entries) | set(self._session)

    # -- use
    def tokenise(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        # A JSON-encoded line break ("...estimate\nArjun") glues the escape letter to the next word, so the name would
        # not be found at a word boundary and would go out in clear (the final check then refuses the whole call).
        # Turning \n, \r and \t escapes into spaces keeps a JSON string valid and lets the name be swapped.
        text = _ESCAPED_SPACE.sub(" ", text)
        st = self._state()

        def swap(kind):
            def f(m):
                v = m.group(0)
                return v if _compact(_fold(v)) in st.by_compact else self._session_token(kind, v)
            return f
        for kind, pat in _PATTERNS:
            text = pat.sub(swap(kind), text)
        if st.whole_wb is not None:
            folded, idx = _fold_map(text)
            spans = []
            for m in st.whole_wb.finditer(folded):
                tok = st.by_compact.get(_compact(m.group(0)))
                if tok:
                    spans.append((m.start(), m.end(), tok))
            for s, e, tok in reversed(spans):
                text = text[:idx[s]] + tok + text[idx[e - 1] + 1:]
        if st.glue is not None:  # AQ1: the glued forms contains_name refuses ("DanielKerr", "Ethan2") are swapped too, so the two agree
            folded, idx = _fold_map(text)
            spans = [(m.start(), m.end(), st.by_compact.get(_compact(m.group(0)))) for m in st.glue.finditer(folded)]
            for s, e, tok in reversed([x for x in spans if x[2]]):
                text = text[:idx[s]] + tok + text[idx[e - 1] + 1:]
        return text

    def detokenise(self, text: str, only=None) -> str:
        """Tokens back to names. With `only` (a set of tokens), just those: any other token stays a token, so a
        reply can never reveal a name that this call did not send."""
        st = self._state()

        def name_of(t: str) -> str:
            if only is not None and t not in only:
                return t
            if t in st.entries:
                return st.entries[t]["name"]
            return self._session.get(t, t)

        def loose(m):  # a model that writes "PERSON 010" or "PERSON-010" for PERSON_010: mapped back only when it is a known token
            t = re.sub(r"[ \u00a0-]", "_", m.group(0))
            return name_of(t) if (t in st.entries or t in self._session) else m.group(0)
        return _LOOSE_TOKEN.sub(loose, _TOKEN.sub(lambda m: name_of(m.group(0)), text))

    def contains_name(self, text: str) -> bool:
        """True if a registered name, e-mail address or phone number is in the text."""
        st = self._state()
        text = unicodedata.normalize("NFKC", text)
        text = _TOKEN.sub(lambda m: " " if (m.group(0) in st.entries or m.group(0) in self._session)
                          else m.group(0), text)
        if any(p.search(text) for k, p in _PATTERNS if k != "number"):
            return True
        folded = _fold_map(text)[0]
        if st.whole_wb is not None and st.whole_wb.search(folded):
            return True
        return st.glue is not None and bool(st.glue.search(_fold_map(_JOIN.sub("", text))[0]))

    def looks_private(self, text: str) -> bool:
        """Stricter, for internet queries and URLs: also true for any vault token (even an
        unknown PERSON_001-style one) and any 8+ digit run (account-like number)."""
        return (self.contains_name(text) or bool(_TOKEN.search(text)) or bool(_NUMBER.search(text)))
