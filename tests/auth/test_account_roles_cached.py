"""AccountStore reads the role names once per change to the permission files, not on every construction (it is built on every request that
reads accounts: Tally, Pulse, access, comments)."""
from sh_platform.auth import accounts


def test_the_role_names_are_parsed_once_while_the_permission_files_do_not_change(monkeypatch, tmp_path):
    real = accounts.load_permissions
    parses = []

    def counting(*a, **k):
        parses.append(1)
        return real(*a, **k)
    monkeypatch.setattr(accounts, "load_permissions", counting)
    monkeypatch.setattr(accounts, "_permission_stamp", lambda: ("same",))
    accounts._role_names.cache_clear()
    stores = [accounts.AccountStore(tmp_path) for _ in range(5)]
    assert len(parses) == 1
    assert stores[0]._roles == set(real().roles)


def test_a_changed_permission_stamp_is_read_again(monkeypatch, tmp_path):
    real = accounts.load_permissions
    parses = []

    def counting(*a, **k):
        parses.append(1)
        return real(*a, **k)
    monkeypatch.setattr(accounts, "load_permissions", counting)
    accounts._role_names.cache_clear()
    monkeypatch.setattr(accounts, "_permission_stamp", lambda: ("before",))
    accounts.AccountStore(tmp_path)
    monkeypatch.setattr(accounts, "_permission_stamp", lambda: ("after",))
    accounts.AccountStore(tmp_path)
    assert len(parses) == 2
