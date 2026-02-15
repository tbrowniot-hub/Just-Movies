from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_NOT_FOUND_MESSAGE = "Copy config.example.json to config.json and edit paths."


def _candidate_paths(cli_config: str | None = None) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    if cli_config:
        candidates.append((Path(cli_config).expanduser(), "cli --config"))
    env_path = os.getenv("MOVIERIPPER_CONFIG")
    if env_path:
        candidates.append((Path(env_path).expanduser(), "MOVIERIPPER_CONFIG env var"))
    candidates.append((Path.cwd() / "config.json", "current working directory"))
    candidates.append((Path.home() / ".movieripper" / "config.json", "~/.movieripper/config.json"))
    return candidates


def resolve_config_path(cli_config: str | None = None) -> tuple[Path, str]:
    for path, reason in _candidate_paths(cli_config):
        if path.exists():
            return path, reason
    raise FileNotFoundError(CONFIG_NOT_FOUND_MESSAGE)


def load_config(cli_config: str | None = None) -> tuple[dict, Path, str]:
    path, reason = resolve_config_path(cli_config)
    return json.loads(path.read_text(encoding="utf-8")), path, reason


def init_config(path: str | None = None) -> Path:
    target = Path(path).expanduser() if path else (Path.cwd() / "config.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Config already exists: {target}")

    example_src = Path(__file__).resolve().parent.parent / "config.example.json"
    target.write_text(example_src.read_text(encoding="utf-8"), encoding="utf-8")
    return target
