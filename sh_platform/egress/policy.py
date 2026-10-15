"""Per-company internet switch and internet allowlist, stored in the company's own plane.
Off unless clearly on; no hosts unless listed."""
import json
import re

from sh_platform.jsonfile import write_json_atomic
from sh_platform.plane import CompanyPlane

FILE = "egress_policy.json"
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+")


class EgressPolicy:
    """`default` is SH_EGRESS_DEFAULT: only the exact text "on" turns a never-configured
    company on. Anything else (including garbage) means off. A corrupt file means off and an
    empty host list."""

    def __init__(self, plane: CompanyPlane, default: str = "off"):
        self.plane = plane
        self._path = plane.area("context") / FILE
        self._default_on = default == "on"

    def _read(self) -> dict:
        """The whole file as a dict; {} when unusable."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def is_internet_allowed(self, module_id: str) -> bool:
        if not self._path.exists():
            return self._default_on
        internet = self._read().get("internet")
        return isinstance(internet, dict) and internet.get(module_id) is True

    def internet_hosts(self) -> list[str]:
        hosts = self._read().get("internet_hosts")
        if not isinstance(hosts, list):
            return []
        return [h for h in hosts if isinstance(h, str) and _HOST.fullmatch(h)]

    def _update(self, **changes) -> None:
        data = self._read()
        data.update(changes)
        write_json_atomic(self._path, data)

    def set_internet(self, module_id: str, enabled: bool) -> None:
        internet = self._read().get("internet")
        internet = dict(internet) if isinstance(internet, dict) else {}
        internet[module_id] = bool(enabled)
        self._update(internet=internet)

    def set_internet_hosts(self, hosts) -> None:
        """Bare lowercase hostnames only: no scheme, port, path or userinfo."""
        hosts = list(hosts)
        if not all(isinstance(h, str) and _HOST.fullmatch(h) for h in hosts):
            raise ValueError("hosts must be bare lowercase host names")
        self._update(internet_hosts=sorted(set(hosts)))

    # V5 D1: the hosts delivery webhooks (Slack, Teams, outgoing) may reach; one entry per configured host, none by default.
    def webhook_hosts(self) -> list[str]:
        hosts = self._read().get("webhook_hosts")
        return [h for h in hosts if isinstance(h, str) and _HOST.fullmatch(h)] if isinstance(hosts, list) else []

    def set_webhook_hosts(self, hosts) -> None:
        hosts = list(hosts)
        if not all(isinstance(h, str) and _HOST.fullmatch(h) for h in hosts):
            raise ValueError("hosts must be bare lowercase host names")
        self._update(webhook_hosts=sorted(set(hosts)))

    # Per-company toggles beyond the internet switch. Stored in the same file; real true only, else off.
    # cloud_push is stored as "cloud_push_requested": nothing reads it as permission until two named
    # approvers exist (a later package), so a request never turns anything on.
    FLAGS = ("connectors", "cloud_push_requested")

    def flag(self, name: str) -> bool:
        return name in self.FLAGS and self._read().get(name) is True

    def set_flag(self, name: str, enabled: bool) -> None:
        if name not in self.FLAGS or not isinstance(enabled, bool):
            raise ValueError("unknown flag or not a boolean")
        self._update(**{name: enabled})
