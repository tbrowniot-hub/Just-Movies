from __future__ import annotations
import argparse
import json
from pathlib import Path

from .clz_index import build_index, load_index
from .queue_ui import QueueBuilderApp
from .watcher import run_queue


def load_config(config_path: str) -> dict:
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


def smoke_test(config_path: str) -> int:
    cfg = load_config(config_path)
    rip_prep_root = Path(cfg["rip_prep_root"])
    rip_staging_root = Path(cfg["rip_staging_root"])
    makemkv_cmd = Path(cfg.get("makemkv_cmd", "makemkvcon64.exe"))

    print(f"MovieRipper loaded from: {Path(__file__).resolve()}")

    ok = True
    for p in (rip_prep_root, rip_staging_root):
        if p.exists():
            print(f"OK path exists: {p}")
        else:
            ok = False
            print(f"MISSING path: {p}")

    if makemkv_cmd.exists():
        print(f"OK MakeMKV exists: {makemkv_cmd}")
    else:
        ok = False
        print(f"MISSING MakeMKV path: {makemkv_cmd}")

    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(prog="movieripper", description="MovieRipper (Windows, queue-driven movie ripping)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("import-master", help="Build index JSON from MASTEREXPORT CSV (must include CLZ Index + IMDb Url)")
    p1.add_argument("--csv", required=True, help="Path to MASTEREXPORT CSV")
    p1.add_argument("--out", required=True, help="Output index JSON path")

    p2 = sub.add_parser("build-queue", help="Open Queue Builder UI (IMDb required) and save movie_queue.json")
    p2.add_argument("--index", required=True, help="Path to index JSON (from import-master)")
    p2.add_argument("--out", default="movie_queue.json", help="Default save path (you can choose another in UI)")

    p3 = sub.add_parser("run-queue", help="Run the queue: wait for disc, rip to RIP_PREP, then move/rename into RIPS_STAGING")
    p3.add_argument("--queue", required=True, help="Path to movie_queue.json")
    p3.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config.json"), help="Path to config.json")

    p4 = sub.add_parser("smoke-test", help="Validate config paths and MakeMKV path without requiring a disc")
    p4.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config.json"), help="Path to config.json")

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
        cfg = load_config(args.config)
        run_queue(cfg, args.queue)
        return

    if args.cmd == "smoke-test":
        raise SystemExit(smoke_test(args.config))


if __name__ == "__main__":
    main()
