from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from threading import Event
from typing import Callable

from .pipeline import Job, process_rip_folder_to_staging, safe_name, write_job
from .ripper import disc_present, rip_disc_all_titles, try_eject, wait_for_disc, wait_for_disc_removed


StatusCallback = Callable[[dict], None]
LogCallback = Callable[[str], None]


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def load_queue(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") or []
    if not isinstance(items, list):
        raise ValueError("Queue JSON missing 'items' list.")
    return items


def run_queue(
    cfg: dict,
    queue_path: str,
    status_callback: StatusCallback | None = None,
    log_callback: LogCallback | None = None,
    stop_event: Event | None = None,
) -> None:
    logger = logging.getLogger("movieripper")

    def emit(message: str) -> None:
        if logger.handlers:
            logger.info(message)
        else:
            print(message)
        if log_callback:
            log_callback(message)

    def update_status(**kwargs: object) -> None:
        if status_callback:
            status_callback(kwargs)

    def should_stop() -> bool:
        return bool(stop_event and stop_event.is_set())

    rip_prep_root = Path(cfg["rip_prep_root"])
    rip_staging_root = Path(cfg["rip_staging_root"])
    makemkv_cmd = cfg.get("makemkv_cmd", "makemkvcon64.exe")
    disc_spec = cfg.get("disc_spec", "disc:0")
    drive_letter = cfg.get("drive_letter", "D:")
    min_length_seconds = int(cfg.get("makemkv_minlength_seconds", 600))
    auto_eject = bool(cfg.get("auto_eject", True))

    ffprobe_cmd = cfg.get("ffprobe_cmd", "ffprobe")
    min_minutes_main = int(cfg.get("min_minutes_main", 45))
    idle_seconds = int(cfg.get("idle_seconds", 180))
    move_mode = cfg.get("move_mode", "move")

    prefer_angle_1 = bool(cfg.get("keeper_policy", {}).get("prefer_angle_1_if_labeled", True))
    duration_tol = float(cfg.get("keeper_policy", {}).get("duration_tolerance_seconds", 2.5))

    queue = load_queue(queue_path)
    if not queue:
        emit("Queue is empty. Nothing to do.")
        update_status(step="done", running=False, message="Queue empty")
        return

    emit(f"MovieRipper queue run starting ({len(queue)} items)")
    emit(f"RIP_PREP:      {rip_prep_root}")
    emit(f"RIPS_STAGING:  {rip_staging_root}")
    emit(f"MakeMKV:       {makemkv_cmd} ({disc_spec})")
    emit(f"Drive letter:  {drive_letter}")

    for i, it in enumerate(queue, start=1):
        if should_stop():
            update_status(step="stopped", running=False)
            emit("Stop requested. Ending queue run.")
            return

        clz_index = int(it["clz_index"])
        title = it["title"]
        year = it.get("year")
        imdb_id = it["imdb_id"]

        emit("\n" + "=" * 90)
        emit(f"[{i}/{len(queue)}] Insert disc for: {title} ({year or ''})  CLZ={clz_index}  IMDb={imdb_id}")
        update_status(step="waiting_for_disc", running=True, current=i, total=len(queue), title=title, clz_index=clz_index, imdb_id=imdb_id)

        if disc_present(makemkv_cmd, disc_spec, configured_drive_letter=drive_letter):
            emit("A disc is already detected in the drive.")
            emit("Please eject/remove it, then insert the correct disc for this queue item.")
            while disc_present(makemkv_cmd, disc_spec, configured_drive_letter=drive_letter):
                if should_stop():
                    update_status(step="stopped", running=False)
                    emit("Stop requested while waiting for current disc removal.")
                    return
                time.sleep(2)

        emit("Waiting for disc...")
        while not wait_for_disc(makemkv_cmd, disc_spec, poll_seconds=3, configured_drive_letter=drive_letter, max_wait_seconds=3):
            if should_stop():
                update_status(step="stopped", running=False)
                emit("Stop requested while waiting for disc insertion.")
                return

        folder_name = safe_name(f"{clz_index}_{title}_{_now_tag()}")
        rip_folder = rip_prep_root / folder_name
        rip_folder.mkdir(parents=True, exist_ok=True)

        job = Job(clz_index=clz_index, title=title, year=year, imdb_id=imdb_id)
        write_job(rip_folder, job)

        update_status(step="ripping", running=True, current=i, total=len(queue), title=title, clz_index=clz_index, imdb_id=imdb_id)
        emit(f"Ripping to {rip_folder}")
        rc, out, err = rip_disc_all_titles(makemkv_cmd, disc_spec, rip_folder, min_length_seconds=min_length_seconds)

        (rip_folder / "_makemkv_stdout.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (rip_folder / "_makemkv_stderr.txt").write_text(err or "", encoding="utf-8", errors="ignore")
        (rip_folder / "_makemkv_returncode.txt").write_text(str(rc), encoding="utf-8")

        mkvs = list(rip_folder.glob("*.mkv"))
        if not mkvs:
            emit("No MKVs found after rip. Skipping this item (check logs in RIP_PREP folder).")
            if auto_eject:
                _ = try_eject(drive_letter=drive_letter, makemkv_cmd=makemkv_cmd, disc_spec=disc_spec)
            continue

        update_status(step="finalizing", running=True, current=i, total=len(queue), title=title, clz_index=clz_index, imdb_id=imdb_id)
        emit("Finalizing rip (waiting for folder to go idle)...")
        t0 = time.time()
        while time.time() - t0 < 1800:
            from .pipeline import is_idle

            if should_stop():
                update_status(step="stopped", running=False)
                emit("Stop requested during finalization wait.")
                return

            if is_idle(rip_folder, idle_seconds=idle_seconds):
                break
            time.sleep(5)

        update_status(step="moving", running=True, current=i, total=len(queue), title=title, clz_index=clz_index, imdb_id=imdb_id)
        emit("Selecting main feature and moving to staging...")
        dest = process_rip_folder_to_staging(
            rip_folder=rip_folder,
            staging_root=rip_staging_root,
            ffprobe_cmd=ffprobe_cmd,
            min_minutes_main=min_minutes_main,
            duration_tol=duration_tol,
            prefer_angle_1=prefer_angle_1,
            move_mode=move_mode,
        )
        emit(f"Done: {dest}")

        if auto_eject:
            update_status(step="ejecting", running=True, current=i, total=len(queue), title=title, clz_index=clz_index, imdb_id=imdb_id)
            ejected = try_eject(drive_letter=drive_letter, makemkv_cmd=makemkv_cmd, disc_spec=disc_spec)
            emit("Eject requested. Waiting for disc to be removed...")
            removed = False
            t0 = time.time()
            while True:
                if should_stop():
                    update_status(step="stopped", running=False)
                    emit("Stop requested during eject/removal wait.")
                    return
                removed = wait_for_disc_removed(
                    makemkv_cmd,
                    disc_spec,
                    poll_seconds=2,
                    timeout_seconds=2,
                    configured_drive_letter=drive_letter,
                )
                if removed:
                    break
                if time.time() - t0 > 60:
                    break

            if not ejected or not removed:
                emit("Warning: eject could not be confirmed. Please eject manually, then continue with the next disc.")
                if not status_callback:  # preserve CLI behavior
                    input("Press Enter after manual eject/removal to continue...")
            else:
                emit("Disc removed.")

    update_status(step="done", running=False)
    emit("\nQueue complete.")
