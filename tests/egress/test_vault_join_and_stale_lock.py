"""Name check joins words only across a hyphen or line break; stale vault locks are broken."""
import json
import logging
import os
import subprocess
import sys
import time

from sh_platform.egress.vault import NameVault


def test_ordinary_spaces_never_join_into_a_name(plane):
    v = NameVault(plane)
    v.register("person", "Ethan Ng")
    v.register("person", "Ethan")
    v.register("person", "Daniel Kerr")
    v.register("company", "Northwind Traders")
    assert not v.contains_name("more than a third of the managers")
    assert not v.contains_name("methane levels")
    for caught in ("Ethan Ng", "ethan", "Et-\nhan", "Et-han", "Et\nhan", "the head, Daniel Kerr, signed",
                   "Daniel-Kerr", "DanielKerr", "ETHAN!", "North\nwind Traders", "North\twind\tTraders"):
        assert v.contains_name(caught), caught


def _old(path, secs):
    t = time.time() - secs
    os.utime(path, (t, t))


def test_empty_lock_left_by_a_killed_owner_is_broken(plane, caplog):
    v = NameVault(plane)
    v._lock.parent.mkdir(parents=True, exist_ok=True)
    v._lock.write_text("")
    _old(v._lock, 5)
    with caplog.at_level(logging.WARNING):
        assert v.register("person", "Ann Lee") == "PERSON_001"
    assert not v._lock.exists() and "empty" in caplog.text


def test_lock_of_dead_pid_is_broken_at_once(plane, caplog):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    v = NameVault(plane)
    v._lock.parent.mkdir(parents=True, exist_ok=True)
    v._lock.write_text(json.dumps({"pid": dead.pid, "token": "dead", "t": time.time()}))
    with caplog.at_level(logging.WARNING):
        assert v.register("person", "Ann Lee") == "PERSON_001"
    assert "owner process gone" in caplog.text


def test_live_lock_older_than_60s_is_broken(plane):
    v = NameVault(plane)
    v._lock.parent.mkdir(parents=True, exist_ok=True)
    v._lock.write_text(json.dumps({"pid": os.getpid(), "token": "old", "t": time.time() - 61}))
    assert v.register("person", "Ann Lee") == "PERSON_001"
