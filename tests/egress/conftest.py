import socket

import pytest

from egress_helpers import Transport
from sh_platform.plane import PlaneStore


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network use in a test")
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)


@pytest.fixture
def store(tmp_path):
    (tmp_path / "data").mkdir()
    return PlaneStore(tmp_path / "data")


@pytest.fixture
def plane(store):
    return store.create("acme-co")


@pytest.fixture
def transport():
    return Transport()
