from __future__ import annotations
import json, shutil, time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .keeper import pick_keeper

@dataclass
class Job:
    """
    One queue item / one disc.
    clz_index: your CLZ Index Number (used for tracking, placed in [brackets] so Plex ignores it)
    imdb_id: tt####### (required for queue eligibility)
    """
    clz_index: int
    title: str
    year: int | None
    imdb_id: str

JOB_FILENAME = ".movieripper.job.json"

def load_job(folder: Path) -> Optional[Job]:
    p = folder / JOB_FILENAME
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return Job(
        clz_index=int(data["clz_index"]),
        title=data["title"],
        year=data.get("year"),
        imdb_id=data["imdb_id"],
    )

def write_job(folder: Path, job: Job) -> None:
    p = folder / JOB_FILENAME
    p.write_text(json.dumps({
        "clz_index": job.clz_index,
        "title": job.title,
        "year": job.year,
        "imdb_id": job.imdb_id
    }, indent=2), encoding="utf-8")

def is_idle(folder: Path, idle_seconds: int) -> bool:
    now = time.time()
    latest = 0.0
    for f in folder.glob("**/*"):
        if f.is_file():
            st = f.stat()
            latest = max(latest, st.st_mtime)
    if latest == 0:
        return False
    return (now - latest) >= idle_seconds

def safe_name(title: str) -> str:
    bad = '<>:"/\\|?*'
    out = ''.join('_' if c in bad else c for c in title)
    while "  " in out:
        out = out.replace("  ", " ")
    return out.strip()

def plex_base_name(job: Job) -> str:
    # Plex-safe base, with CLZ index in [brackets] (ignored by Plex) and IMDb tag in {curly braces}
    base = f"{job.title}"
    if job.year:
        base += f" ({job.year})"
    base += f" [clz-{job.clz_index}]"
    base += f" {{imdb-{job.imdb_id}}}"
    return safe_name(base)

def process_rip_folder_to_staging(
    rip_folder: Path,
    staging_root: Path,
    ffprobe_cmd: str,
    min_minutes_main: int,
    duration_tol: float,
    prefer_angle_1: bool,
    move_mode: str
) -> Path:
    """
    - Expects rip_folder to contain MKVs and a .movieripper.job.json
    - Picks keeper
    - Creates: staging_root\<PlexFolderName>\PlexFileName.mkv
    """
    job = load_job(rip_folder)
    if not job:
        raise RuntimeError(f"No job file found in {rip_folder}.")
    mkvs = [str(p) for p in rip_folder.glob("*.mkv")]
    if not mkvs:
        raise RuntimeError(f"No .mkv files found in {rip_folder}.")

    keeper = pick_keeper(
        mkvs,
        ffprobe_cmd=ffprobe_cmd,
        min_minutes=min_minutes_main,
        duration_tol=duration_tol,
        prefer_angle_1=prefer_angle_1
    )

    base = plex_base_name(job)
    dest_dir = staging_root / base
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / (base + Path(keeper.path).suffix)
    if dest_path.exists():
        raise RuntimeError(f"Destination already exists: {dest_path}")

    if move_mode.lower() == "copy":
        shutil.copy2(keeper.path, dest_path)
    else:
        shutil.move(keeper.path, dest_path)

    receipt = {
        "rip_folder": str(rip_folder),
        "keeper_source": keeper.path,
        "keeper_dest": str(dest_path),
        "clz_index": job.clz_index,
        "title": job.title,
        "year": job.year,
        "imdb_id": job.imdb_id
    }
    (rip_folder / ".movieripper.receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return dest_path
