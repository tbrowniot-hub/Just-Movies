import json
from pathlib import Path

from MovieRipper.config import resolve_config_path


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
