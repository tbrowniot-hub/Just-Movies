from __future__ import annotations
import re
import subprocess, time
from pathlib import Path
from typing import Optional

class MakeMKVError(RuntimeError):
    pass

def _run(cmd: list[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def _get_info_text(makemkv_cmd: str, disc_spec: str) -> str:
    try:
        p = _run([makemkv_cmd, "-r", "info", disc_spec], timeout=600)
    except Exception:
        return ""
    return (p.stdout or "") + "\n" + (p.stderr or "")

def disc_present(makemkv_cmd: str, disc_spec: str) -> bool:
    """
    Returns True only when MakeMKV can open the disc and reports one or more titles.

    IMPORTANT: MakeMKV always prints DRV: lines (drive enumeration) even when there is NO disc.
    So we key off TCOUNT: > 0 (or CINFO present as a fallback).
    """
    txt = _get_info_text(makemkv_cmd, disc_spec)
    if not txt:
        return False

    m = re.search(r"TCOUNT:(\d+)", txt)
    if m:
        return int(m.group(1)) > 0

    # Fallback: some builds may omit TCOUNT but include CINFO/TINFO when disc is open.
    if "CINFO:" in txt or "TINFO:" in txt:
        return True

    return False

def wait_for_disc(makemkv_cmd: str, disc_spec: str, poll_seconds: int = 3) -> None:
    while True:
        if disc_present(makemkv_cmd, disc_spec):
            return
        time.sleep(poll_seconds)

def wait_for_disc_removed(makemkv_cmd: str, disc_spec: str, poll_seconds: int = 2, timeout_seconds: int = 0) -> bool:
    """
    Wait until no disc is present. If timeout_seconds is 0, wait indefinitely.
    Returns True if removed, False if timed out.
    """
    t0 = time.time()
    while True:
        if not disc_present(makemkv_cmd, disc_spec):
            return True
        if timeout_seconds and (time.time() - t0) > timeout_seconds:
            return False
        time.sleep(poll_seconds)

def rip_disc_all_titles(
    makemkv_cmd: str,
    disc_spec: str,
    out_dir: Path,
    min_length_seconds: int = 600
) -> tuple[int, str, str]:
    """
    Rips ALL titles (we will keeper-pick later). Returns (returncode, stdout, stderr).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [makemkv_cmd, "-r", "mkv", disc_spec, "all", str(out_dir), f"--minlength={int(min_length_seconds)}"]
    p = _run(cmd)
    return p.returncode, p.stdout, p.stderr

def _drive_letter_from_info(txt: str) -> Optional[str]:
    # DRV:0,2,999,1,"...","VOLUME_LABEL","D:"
    m = re.search(r'DRV:\d+,\d+,\d+,\d+,"[^"]*","[^"]*","([^"]+)"', txt)
    if m:
        return m.group(1)
    return None

def try_eject(makemkv_cmd: str, disc_spec: str) -> None:
    """
    Best-effort eject. We try:
      1) MakeMKV eject
      2) Windows Shell eject for the detected drive letter (e.g., D:)
    """
    # 1) MakeMKV eject
    try:
        _run([makemkv_cmd, "-r", "eject", disc_spec], timeout=30)
    except Exception:
        pass

    # 2) Windows Shell eject (more reliable on some drives)
    try:
        txt = _get_info_text(makemkv_cmd, disc_spec)
        drive = _drive_letter_from_info(txt) if txt else None
        if drive:
            ps = f"(New-Object -ComObject Shell.Application).NameSpace(17).ParseName('{drive}').InvokeVerb('Eject')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
    except Exception:
        pass
