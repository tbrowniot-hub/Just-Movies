from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .clz_index import build_index, load_index
from .config import (
    CONFIG_NOT_FOUND_MESSAGE,
    init_config,
    load_config,
    normalize_config,
    resolve_config_path,
    validate_config,
)
from .logging_setup import configure_logging
from .queue_ui import QueueBuilderApp
from .watcher import run_queue


def smoke_test(config_path: str | None) -> int:
    cfg, resolved, reason = load_config(config_path)
    report = validate_config(cfg)
    normalized = normalize_config(cfg)
    rip_prep_root = Path(normalized["rips_staging_root"])
    rip_staging_root = Path(normalized["final_movies_root"])
    makemkv_cmd = Path(normalized.get("makemkv_cmd", "makemkvcon64.exe"))

    print(f"Config: {resolved} ({reason})")
    print(f"MovieRipper loaded from: {Path(__file__).resolve()}")

    ok = not report["errors"]
    for p in (rip_prep_root, rip_staging_root):
        if p.exists():
            print(f"OK path exists: {p}")
        else:
            ok = False
            print(f"MISSING path: {p}")

    for warning in report["warnings"]:
        print(f"WARNING: {warning}")

    for error in report["errors"]:
        print(f"ERROR: {error}")

    if makemkv_cmd.exists():
        print(f"OK MakeMKV exists: {makemkv_cmd}")
    else:
        ok = False
        print(f"MISSING MakeMKV path: {makemkv_cmd}")

    return 0 if ok else 1


def _start_web(host: str, port: int) -> int:
    try:
        import uvicorn
        from .webapp.app import create_app
    except ImportError:
        print('Web UI requires extras. Install with: pip install -e ".[web]"')
        return 1

    uvicorn.run(create_app(), host=host, port=port)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(prog="movieripper", description="MovieRipper (Windows, queue-driven movie ripping)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("import-master", help="Build index JSON from MASTEREXPORT CSV (must include CLZ Index + IMDb Url)")
    p1.add_argument("--csv", required=True, help="Path to MASTEREXPORT CSV")
    p1.add_argument("--out", required=True, help="Output index JSON path")

    p2 = sub.add_parser("build-queue", help="Open Queue Builder UI (IMDb required) and save movie_queue.json")
    p2.add_argument("--index", required=True, help="Path to index JSON (from import-master)")
    p2.add_argument("--out", default="movie_queue.json", help="Default save path (you can choose another in UI)")

    p3 = sub.add_parser("run-queue", help="Run the queue: wait for disc, rip to RIP_PREP, then move/rename into RIPS_STAGING")
    p3.add_argument("--queue", required=True, help="Path to movie_queue.json")
    p3.add_argument("--config", default=None, help="Path to config.json")

    p4 = sub.add_parser("smoke-test", help="Validate config paths and MakeMKV path without requiring a disc")
    p4.add_argument("--config", default=None, help="Path to config.json")

    p5 = sub.add_parser("config", help="Config discovery and initialization")
    config_sub = p5.add_subparsers(dest="config_cmd", required=True)
    p5w = config_sub.add_parser("where", help="Show resolved config path and discovery source")
    p5w.add_argument("--config", default=None, help="Path to config.json")
    p5i = config_sub.add_parser("init", help="Write config.example.json to target path")
    p5i.add_argument("--path", default=None, help="Target path (default: ./config.json)")

    p6 = sub.add_parser("web", help="Run local web control panel")
    p6.add_argument("--host", default="127.0.0.1", help="Host bind (default localhost only)")
    p6.add_argument("--port", default=8765, type=int, help="Port")

    args = ap.parse_args()

    if args.cmd == "import-master":
        build_index(args.csv, args.out)
        print(f"Wrote index: {args.out}")
        return

    if args.cmd == "build-queue":
        idx = load_index(args.index)
        app = QueueBuilderApp(idx, default_save_path=Path(args.out))
        app.mainloop()
        return

    if args.cmd == "run-queue":
        cfg, _, _ = load_config(args.config)
        configure_logging(cfg.get("log_dir"))
        run_queue(cfg, args.queue)
        return

    if args.cmd == "smoke-test":
        raise SystemExit(smoke_test(args.config))

    if args.cmd == "config":
        if args.config_cmd == "where":
            try:
                path, reason = resolve_config_path(args.config)
            except FileNotFoundError:
                raise SystemExit(CONFIG_NOT_FOUND_MESSAGE)
            print(f"{path} ({reason})")
            return
        if args.config_cmd == "init":
            try:
                target = init_config(args.path)
            except FileExistsError as exc:
                raise SystemExit(str(exc))
            print(f"Wrote config template: {target}")
            return

    if args.cmd == "web":
        raise SystemExit(_start_web(args.host, args.port))


if __name__ == "__main__":
    main()
