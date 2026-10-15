"""The three connector kinds. Each opens a Session: items(checkpoint) -> (items, new_checkpoint), read(item) -> bytes, probe(), close().
Every outbound connection goes through `gate.call(kind, host, fn)` (egress allowlist plus log). `F` holds the injectable
clients (tests pass stubs; defaults use imaplib, paramiko if installed, httpx)."""
from __future__ import annotations

import email
import fnmatch
import json
import ssl
import stat
from email import policy
from urllib.parse import quote, urlsplit


class ConnectorError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def matches(name: str, pattern: str) -> bool:
    return any(fnmatch.fnmatch(name.lower(), p.strip().lower()) for p in pattern.split(";") if p.strip())


# ---- default clients (not used in tests)
def _imap(host, port):
    import imaplib
    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30)


class _Sftp:
    def __init__(self, host, port, user, password, key_file):
        try:
            import paramiko
        except ImportError:
            raise ConnectorError("unavailable", "SFTP needs the paramiko package, which is not installed on this server.") from None
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.RejectPolicy())  # unknown servers are refused, never trusted silently
        self.ssh.connect(host, port=port, username=user, password=password, key_filename=key_file, timeout=30,
                         allow_agent=False, look_for_keys=False)
        self.sftp = self.ssh.open_sftp()

    def listdir_attr(self, p):
        return self.sftp.listdir_attr(p)

    def read(self, p):
        with self.sftp.open(p, "rb") as f:
            return f.read()

    def close(self):
        self.ssh.close()


def _http(method, url, headers, data=None):
    import httpx
    r = httpx.request(method, url, headers=headers, content=data, timeout=60, follow_redirects=False)
    return r.status_code, r.content


DEFAULTS = {"imap": _imap, "sftp": _Sftp, "http": _http}


# ---- IMAP over TLS, attachments only
class Imap:
    def __init__(self, spec, env, gate, F):
        self.spec, self.pattern, self.box = spec, spec["file_pattern"], None
        self.box = gate.call("imap", spec["host"], lambda: F["imap"](spec["host"], 993))
        try:
            self.box.login(env("user"), env("password"))
            typ, _ = self.box.select(spec["params"]["mailbox"], readonly=True)  # read only: nothing is marked read or moved
            if typ != "OK":
                raise ConnectorError("not_found", "That mailbox folder could not be opened.")
        except ConnectorError:
            self.close()
            raise
        except Exception:
            self.close()
            raise ConnectorError("login_failed", "The mail server refused the sign-in or the folder.") from None

    def probe(self):
        return {"message": "Signed in and opened the folder (read only)."}

    def items(self, ck):
        last = int((ck or {}).get("uid", 0))
        _, data = self.box.uid("SEARCH", None, f"UID {last + 1}:*")
        uids = sorted(u for u in (int(x) for x in (data[0] or b"").split()) if u > last)
        out = []
        for u in uids:
            _, d = self.box.uid("FETCH", str(u), "(BODY.PEEK[])")
            msg = email.message_from_bytes(d[0][1], policy=policy.default)
            for part in msg.walk():
                fn = part.get_filename()
                if fn and not part.is_multipart() and matches(fn, self.pattern):
                    # ponytail: attachments are held in memory per run (25 MB cap in landing); stream if mailboxes grow
                    payload = part.get_payload(decode=True) or b""
                    out.append({"key": f"{u}:{fn}", "name": fn, "size": len(payload), "_data": payload})
        return out, ({"uid": uids[-1]} if uids else ck or {})

    def read(self, item):
        return item["_data"]

    def close(self):
        try:
            self.box.logout()
        except Exception:  # noqa: BLE001
            pass


# ---- SFTP pull
class Sftp:
    def __init__(self, spec, env, gate, F):
        self.spec, self.path = spec, spec["params"]["remote_path"].rstrip("/") or "/"
        c = spec["credentials"]
        key = env("key_file") if "key_file" in c else None
        pw = env("password") if "password" in c else None
        user = env("user")
        try:
            self.c = gate.call("sftp", spec["host"], lambda: F["sftp"](spec["host"], int(spec["params"]["port"]), user, pw, key))
        except (ConnectorError, *_blocked()):
            raise
        except Exception:
            raise ConnectorError("login_failed", "The SFTP server refused the connection or the sign-in.") from None

    def probe(self):
        n = len(self.c.listdir_attr(self.path))
        return {"message": f"Connected and listed the folder (read only): {n} entries."}

    def items(self, ck):
        seen = set((ck or {}).get("seen", []))
        out = []
        for a in sorted(self.c.listdir_attr(self.path), key=lambda a: a.filename):
            key = f"{a.filename}:{int(a.st_mtime or 0)}:{a.st_size}"
            if not stat.S_ISDIR(getattr(a, "st_mode", 0) or 0) and matches(a.filename, self.spec["file_pattern"]) and key not in seen:
                out.append({"key": key, "name": a.filename, "size": a.st_size})
        return out, {"seen": (sorted(seen) + [i["key"] for i in out])[-5000:]}

    def read(self, item):
        return self.c.read(f"{self.path}/{item['name']}")

    def close(self):
        try:
            self.c.close()
        except Exception:  # noqa: BLE001
            pass


def _blocked():
    from sh_platform.egress.errors import EgressBlocked
    return (EgressBlocked,)


# ---- Microsoft Graph (SharePoint / OneDrive). Needs graph.microsoft.com, login.microsoftonline.com and the download host on the allowlist.
class Graph:
    LOGIN = "login.microsoftonline.com"

    def __init__(self, spec, env, gate, F):
        self.spec, self.gate, self.http = spec, gate, F["http"]
        body = "&".join(f"{k}={quote(v, safe='')}" for k, v in (
            ("client_id", env("client_id")), ("client_secret", env("client_secret")),
            ("scope", "https://graph.microsoft.com/.default"), ("grant_type", "client_credentials"))).encode()
        url = f"https://{self.LOGIN}/{quote(env('tenant'), safe='')}/oauth2/v2.0/token"
        st, raw = gate.call("graph", self.LOGIN, lambda: self.http("POST", url, {"Content-Type": "application/x-www-form-urlencoded"}, body))
        try:
            self.tok = json.loads(raw)["access_token"] if st == 200 else None
        except (ValueError, KeyError, TypeError):
            self.tok = None
        if not self.tok:
            raise ConnectorError("login_failed", "Microsoft refused the sign-in. Check the tenant, client id and secret variables.")

    def _get(self, host, url, auth=True):
        st, raw = self.gate.call("graph", host, lambda: self.http("GET", url, {"Authorization": f"Bearer {self.tok}"} if auth else {}))
        if st != 200:
            raise ConnectorError("not_found" if st == 404 else "failed", f"The cloud folder answered with status {st}.")
        return raw

    def _children(self):
        p, d = self.spec["params"], self.spec["host"]
        folder = quote(p.get("folder", "").strip("/"), safe="/")
        url = f"https://{d}/v1.0/drives/{quote(p['drive_id'], safe='')}/" + (f"root:/{folder}:/children" if folder else "root/children")
        for _ in range(20):  # page cap
            j = json.loads(self._get(d, url))
            yield from j.get("value", [])
            url = j.get("@odata.nextLink")
            if not url or urlsplit(url).hostname != d:
                return

    def probe(self):
        n = sum(1 for _ in self._children())
        return {"message": f"Signed in and listed the folder (read only): {n} entries."}

    def items(self, ck):
        seen = set((ck or {}).get("seen", []))
        out = []
        for it in self._children():
            key = f"{it.get('id')}:{it.get('eTag', '')}"
            if "file" in it and matches(it.get("name", ""), self.spec["file_pattern"]) and key not in seen and it.get("@microsoft.graph.downloadUrl"):
                out.append({"key": key, "name": it["name"], "size": it.get("size", 0), "_url": it["@microsoft.graph.downloadUrl"]})
        return out, {"seen": (sorted(seen) + [i["key"] for i in out])[-5000:]}

    def read(self, item):  # the download URL is pre-signed and lives on another host: it is checked and logged like any other
        return self._get(urlsplit(item["_url"]).hostname or "", item["_url"], auth=False)

    def close(self):
        pass


SESSIONS = {"imap": Imap, "sftp": Sftp, "graph": Graph}
