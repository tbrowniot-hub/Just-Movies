from __future__ import annotations
import json
import time
from pathlib import Path

from .pipeline import Job, write_job, process_rip_folder_to_staging, safe_name
from .ripper import wait_for_disc, wait_for_disc_removed, disc_present, rip_disc_all_titles, try_eject


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def load_queue(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") or []
    if not isinstance(items, list):
        raise ValueError("Queue JSON missing 'items' list.")
    return items


def run_queue(cfg: dict, queue_path: str) -> None:
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
        print("Queue is empty. Nothing to do.")
        return

    print(f"MovieRipper queue run starting ({len(queue)} items)")
    print(f"RIP_PREP:      {rip_prep_root}")
    print(f"RIPS_STAGING:  {rip_staging_root}")
    print(f"MakeMKV:       {makemkv_cmd} ({disc_spec})")
    print(f"Drive letter:  {drive_letter}")

    for i, it in enumerate(queue, start=1):
        clz_index = int(it["clz_index"])
        title = it["title"]
        year = it.get("year")
        imdb_id = it["imdb_id"]

        print("\n" + "=" * 90)
        print(f"[{i}/{len(queue)}] Insert disc for: {title} ({year or ''})  CLZ={clz_index}  IMDb={imdb_id}")
        if disc_present(makemkv_cmd, disc_spec, configured_drive_letter=drive_letter):
            print("A disc is already detected in the drive.")
            print("Please eject/remove it, then insert the correct disc for this queue item.")
            wait_for_disc_removed(
                makemkv_cmd,
                disc_spec,
                poll_seconds=2,
                timeout_seconds=0,
                configured_drive_letter=drive_letter,
            )

        print("Waiting for disc...")
        wait_for_disc(makemkv_cmd, disc_spec, configured_drive_letter=drive_letter)

        folder_name = safe_name(f"{clz_index}_{title}_{_now_tag()}")
        rip_folder = rip_prep_root / folder_name
        rip_folder.mkdir(parents=True, exist_ok=True)

        job = Job(clz_index=clz_index, title=title, year=year, imdb_id=imdb_id)
        write_job(rip_folder, job)

        print(f"Ripping to {rip_folder}")
        rc, out, err = rip_disc_all_titles(makemkv_cmd, disc_spec, rip_folder, min_length_seconds=min_length_seconds)

        (rip_folder / "_makemkv_stdout.txt").write_text(out or "", encoding="utf-8", errors="ignore")
        (rip_folder / "_makemkv_stderr.txt").write_text(err or "", encoding="utf-8", errors="ignore")
        (rip_folder / "_makemkv_returncode.txt").write_text(str(rc), encoding="utf-8")

        mkvs = list(rip_folder.glob("*.mkv"))
        if not mkvs:
            print("No MKVs found after rip. Skipping this item (check logs in RIP_PREP folder).")
            if auto_eject:
                _ = try_eject(drive_letter=drive_letter, makemkv_cmd=makemkv_cmd, disc_spec=disc_spec)
            continue

        print("Finalizing rip (waiting for folder to go idle)...")
        t0 = time.time()
        while time.time() - t0 < 1800:
            from .pipeline import is_idle

            if is_idle(rip_folder, idle_seconds=idle_seconds):
                break
            time.sleep(5)

        print("Selecting main feature and moving to staging...")
        dest = process_rip_folder_to_staging(
            rip_folder=rip_folder,
            staging_root=rip_staging_root,
            ffprobe_cmd=ffprobe_cmd,
            min_minutes_main=min_minutes_main,
            duration_tol=duration_tol,
            prefer_angle_1=prefer_angle_1,
            move_mode=move_mode,
        )
        print(f"Done: {dest}")

        if auto_eject:
            ejected = try_eject(drive_letter=drive_letter, makemkv_cmd=makemkv_cmd, disc_spec=disc_spec)
            print("Eject requested. Waiting for disc to be removed...")
            removed = wait_for_disc_removed(
                makemkv_cmd,
                disc_spec,
                poll_seconds=2,
                timeout_seconds=60,
                configured_drive_letter=drive_letter,
            )
            if not ejected or not removed:
                print(
                    "Warning: eject could not be confirmed. Please eject manually, then continue with the next disc."
                )
                input("Press Enter after manual eject/removal to continue...")
            else:
                print("Disc removed.")

    print("\nQueue complete.")
