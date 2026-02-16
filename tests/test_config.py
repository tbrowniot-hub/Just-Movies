from MovieRipper.config import resolve_config_path, validate_config


def test_config_discovery_env_beats_cwd(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "config.json").write_text("{}", encoding="utf-8")

    env_cfg = tmp_path / "env_config.json"
    env_cfg.write_text("{}", encoding="utf-8")

    monkeypatch.chdir(cwd)
    monkeypatch.setenv("MOVIERIPPER_CONFIG", str(env_cfg))

    resolved, reason = resolve_config_path(None)
    assert resolved == env_cfg
    assert "env var" in reason


def test_config_discovery_cli_beats_env(tmp_path, monkeypatch):
    env_cfg = tmp_path / "env_config.json"
    env_cfg.write_text("{}", encoding="utf-8")
    cli_cfg = tmp_path / "cli_config.json"
    cli_cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MOVIERIPPER_CONFIG", str(env_cfg))

    resolved, reason = resolve_config_path(str(cli_cfg))
    assert resolved == cli_cfg
    assert "cli" in reason


def test_validate_config_accepts_legacy_alias_keys(tmp_path):
    cfg = {
        "rip_prep_root": str(tmp_path / "rip"),
        "rip_staging_root": str(tmp_path / "final"),
        "makemkv_cmd": str(tmp_path / "makemkvcon64.exe"),
    }
    report = validate_config(cfg)

    assert report["valid"] is True
    assert report["resolved"]["rips_staging_root"] == cfg["rip_prep_root"]
    assert report["resolved"]["final_movies_root"] == cfg["rip_staging_root"]
    assert report["warnings"]


def test_validate_config_requires_new_roots_or_aliases():
    report = validate_config({"makemkv_cmd": "makemkvcon64.exe"})
    assert report["valid"] is False
    assert any("rips_staging_root" in err for err in report["errors"])
    assert any("final_movies_root" in err for err in report["errors"])
