from sh_platform.settings import Settings, load_settings


def test_health_returns_ok_only(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings_defaults(tmp_path):
    s = load_settings({}, env_file=tmp_path / "missing.env")
    assert s.mode == "dev"
    assert s.egress_default == "off"
    assert s.data_root == "./data"


def test_settings_repr_hides_secret(tmp_path):
    s = load_settings({"SH_SESSION_SECRET": "s3cr3t-value"}, env_file=tmp_path / "none.env")
    assert s.session_secret == "s3cr3t-value"
    assert "s3cr3t-value" not in repr(s)
    assert isinstance(s, Settings)


def test_env_file_read_for_known_names_only(tmp_path):
    f = tmp_path / ".env"
    f.write_text("SH_MODE=prod\nOTHER=x\n", encoding="utf-8")
    assert load_settings({}, env_file=f).mode == "prod"
    assert load_settings({"SH_MODE": "dev"}, env_file=f).mode == "dev"


def test_docs_routes_are_off(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_model_env_reads_only_model_names_from_the_env_file_and_the_process_wins(tmp_path):
    from sh_platform.settings import load_model_env
    f = tmp_path / ".env"
    f.write_text("GOOGLE_API_KEY=FAKE-file-key\nSH_MODEL_NAME=m-1\nSH_MODEL_PROVIDER=gemini\nSH_SESSION_SECRET=x\n"
                 "OTHER=1\nOPENROUTER_API_KEY=\n", encoding="utf-8")
    got = load_model_env({}, env_file=f)
    assert got == {"GOOGLE_API_KEY": "FAKE-file-key", "SH_MODEL_NAME": "m-1", "SH_MODEL_PROVIDER": "gemini"}
    got = load_model_env({"GOOGLE_API_KEY": "FAKE-proc-key", "SH_MODEL_FAST": "f", "PATH": "p"}, env_file=f)
    assert got["GOOGLE_API_KEY"] == "FAKE-proc-key" and got["SH_MODEL_FAST"] == "f" and "PATH" not in got
    assert load_model_env({}, env_file=tmp_path / "none.env") == {}


def test_an_empty_environment_value_beats_the_env_file(tmp_path):
    from sh_platform.settings import load_model_env
    f = tmp_path / ".env"
    f.write_text("GOOGLE_API_KEY=FAKE-file-key\nOPENROUTER_API_KEY=FAKE-file-key2\nSH_MODEL_PROVIDER=gemini\n", encoding="utf-8")
    got = load_model_env({"GOOGLE_API_KEY": "", "OPENROUTER_API_KEY": ""}, env_file=f)
    assert got["GOOGLE_API_KEY"] == "" and got["OPENROUTER_API_KEY"] == ""
    from sh_platform.egress.providers import select_provider
    assert select_provider(got) is None  # set but empty: that provider is off, the file key is not used


def test_the_off_switch_is_accepted_from_the_file_and_gives_no_client(tmp_path):
    from sh_platform.egress.providers import build_model_client, key_status, select_provider
    from sh_platform.plane import PlaneStore
    from sh_platform.settings import load_model_env
    f = tmp_path / ".env"
    f.write_text("GOOGLE_API_KEY=FAKE-file-key\nSH_MODEL_PROVIDER=off\n", encoding="utf-8")
    env = load_model_env({}, env_file=f)
    assert env["SH_MODEL_PROVIDER"] == "off" and select_provider(env) is None
    assert key_status(env)["provider"] is None and key_status(env)["off"] is True
    (tmp_path / "data").mkdir()
    plane = PlaneStore(tmp_path / "data").create("acme-co")
    assert build_model_client(plane, env) is None
    assert build_model_client(plane, {"GOOGLE_API_KEY": "FAKE", "SH_MODEL_PROVIDER": " OFF "}) is None
