from sh_platform.egress.policy import EgressPolicy


def _file(plane):
    return plane.area("context") / "egress_policy.json"


def test_default_off_when_missing(plane):
    assert EgressPolicy(plane).is_internet_allowed("m1_intent") is False


def test_corrupt_file_denies(plane):
    _file(plane).write_text("{not json")
    assert EgressPolicy(plane).is_internet_allowed("m1_intent") is False
    _file(plane).write_text('{"internet": {"m1_intent": "yes"}}')
    assert EgressPolicy(plane).is_internet_allowed("m1_intent") is False


def test_unknown_module_and_garbage_default_deny(plane):
    p = EgressPolicy(plane, default="garbage")
    assert p.is_internet_allowed("whatever") is False
    p.set_internet("m1_intent", True)
    assert p.is_internet_allowed("other") is False


def test_default_on_only_for_exact_on_and_never_configured(plane):
    assert EgressPolicy(plane, default="on").is_internet_allowed("m1") is True
    assert EgressPolicy(plane, default="ON ").is_internet_allowed("m1") is False
    p = EgressPolicy(plane, default="on")
    p.set_internet("m2", True)  # now configured: an unlisted module is off again
    assert p.is_internet_allowed("m1") is False


def test_on_for_one_module_and_one_company_only(plane, store):
    other = store.create("beta-co")
    p = EgressPolicy(plane)
    p.set_internet("m1_intent", True)
    assert p.is_internet_allowed("m1_intent") is True
    assert p.is_internet_allowed("m2_baseline") is False
    assert EgressPolicy(other).is_internet_allowed("m1_intent") is False
    assert EgressPolicy(plane).is_internet_allowed("m1_intent") is True  # persisted
    p.set_internet("m1_intent", False)
    assert EgressPolicy(plane).is_internet_allowed("m1_intent") is False
