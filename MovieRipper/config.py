from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_NOT_FOUND_MESSAGE = "Copy config.example.json to config.json and edit paths."

ROOT_ALIASES: dict[str, tuple[str, ...]] = {
    "rips_staging_root": ("rip_prep_root",),
    "final_movies_root": ("rip_staging_root",),
}


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


def resolve_path_setting(config_json: dict[str, Any], key: str) -> str | None:
    value = config_json.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    for alias in ROOT_ALIASES.get(key, ()):
        alias_value = config_json.get(alias)
        if isinstance(alias_value, str) and alias_value.strip():
            return alias_value.strip()
    return None


def normalize_config(config_json: dict[str, Any]) -> dict[str, Any]:
    out = dict(config_json)
    for key in ROOT_ALIASES:
        resolved = resolve_path_setting(out, key)
        if resolved:
            out[key] = resolved
    return out


def validate_config(config_json: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_config(config_json)
    errors: list[str] = []
    warnings: list[str] = []
    resolved_paths: dict[str, str] = {}

    for key in ROOT_ALIASES:
        value = normalized.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"Missing required path '{key}' (accepted aliases: {', '.join(ROOT_ALIASES[key])})."
            )
            continue
        resolved_paths[key] = value
        if not Path(value).expanduser().exists():
            warnings.append(f"Configured path does not exist: {key} -> {value}")

    makemkv_cmd = normalized.get("makemkv_cmd")
    checks = {
        "rips_staging_root_exists": bool(resolved_paths.get("rips_staging_root"))
        and Path(resolved_paths["rips_staging_root"]).expanduser().exists(),
        "final_movies_root_exists": bool(resolved_paths.get("final_movies_root"))
        and Path(resolved_paths["final_movies_root"]).expanduser().exists(),
        "makemkv_exists": bool(makemkv_cmd)
        and Path(str(makemkv_cmd)).expanduser().exists(),
        "final_parent_exists": bool(resolved_paths.get("final_movies_root"))
        and Path(resolved_paths["final_movies_root"]).expanduser().parent.exists(),
    }

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "resolved": resolved_paths,
        "normalized_config": normalized,
    }


def init_config(path: str | None = None) -> Path:
    target = Path(path).expanduser() if path else (Path.cwd() / "config.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Config already exists: {target}")

    example_src = Path(__file__).resolve().parent.parent / "config.example.json"
    target.write_text(example_src.read_text(encoding="utf-8"), encoding="utf-8")
    return target
