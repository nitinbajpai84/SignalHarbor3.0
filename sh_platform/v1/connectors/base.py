"""The connector contract (W1, docs/v3/PROGRAM-GAPS.md). A connector fetches what a bank, custodian or inbox has sent since a date and hands
back files. The files go into the office's dropbox like any file a person drops, so the pack's readers read them with receipts, the review queue
and the rule checks apply, and nothing has a second path into the warehouse.

A file-format connector (MT940, camt.053, MT535/536, BAI2) is a reader in the pack (`v3_pack_readers.kind_of` plus its reader); its connector
here only fetches the files (from an SFTP folder or a local folder). An API connector (Plaid, Saxo, GoCardless, a bank sandbox) turns the
provider's JSON into one of those standard files or a pack CSV, so the readers stay the one way in. Every network call goes through the egress
gateway, off by default per company; a connector never reads a key from anywhere but the environment variable it names."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class Fetched:
    name: str  # the file name it lands under in the dropbox (dated, so folder_month places it)
    data: bytes
    source: str  # where it came from, said on the receipt ("Saxo OpenAPI simulation, account SIM-1234")


@dataclass
class Status:
    connector: str
    ok: bool
    files: int = 0
    message: str = ""  # plain words for the Connections page
    missing: list[str] = field(default_factory=list)  # environment variable names not set (never their values)


class Connector(Protocol):
    id: str  # "mt940", "saxo" ...
    label: str  # "SWIFT MT940 bank statements"
    kind: str  # "file format" | "api" | "inbox" | "sftp"
    env: tuple[str, ...]  # environment variable names it needs; empty for file formats

    def fetch(self, since: date) -> list[Fetched]: ...


REGISTRY: dict[str, Connector] = {}


def register(c: Connector) -> Connector:
    REGISTRY[c.id] = c
    return c


def run(plane, c: Connector, since: date) -> Status:
    """Fetch and drop. A connector that lacks its settings reports which names are missing and fetches nothing."""
    import os

    from sh_platform.v1 import v3_harbor as H
    missing = [n for n in c.env if not os.environ.get(n)]
    if missing:
        return Status(c.id, False, message="Not connected yet: settings missing", missing=missing)
    got = c.fetch(since)
    for f in got:
        H.drop(plane, f.name, f.data)
    return Status(c.id, True, len(got), f"{len(got)} file(s) received")
