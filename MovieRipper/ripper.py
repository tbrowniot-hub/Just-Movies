from __future__ import annotations
import re
import subprocess
import time
from pathlib import Path
from typing import Optional


class MakeMKVError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _parse_drive_letter(disc_spec: str, configured_drive_letter: Optional[str]) -> str:
    if configured_drive_letter:
        letter = configured_drive_letter.strip().rstrip('\\').upper()
        if not letter.endswith(':'):
            letter += ':'
        return letter
    m = re.match(r"drive:([A-Za-z])", str(disc_spec or ""))
    if m:
        return f"{m.group(1).upper()}:"
    return "D:"


def _drive_has_media(drive_letter: str) -> bool:
    path = f"{drive_letter}\\"
    # On Windows, Test-Path is a practical signal for optical media presence.
    ps = f"if (Test-Path '{path}') {{ exit 0 }} else {{ exit 1 }}"
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=8,
        )
        return p.returncode == 0
    except Exception:
        return False


def _get_info_text(makemkv_cmd: str, disc_spec: str, timeout_seconds: int = 20) -> tuple[str, bool]:
    try:
        p = _run([makemkv_cmd, "-r", "info", disc_spec], timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return "", True
    except Exception:
        return "", False
    return (p.stdout or "") + "\n" + (p.stderr or ""), False


def disc_present(
    makemkv_cmd: str,
    disc_spec: str,
    configured_drive_letter: Optional[str] = None,
    info_timeout_seconds: int = 20,
) -> bool:
    """
    Returns True when MakeMKV sees titles, or when info timed out but drive media is present.
    """
    txt, timed_out = _get_info_text(makemkv_cmd, disc_spec, timeout_seconds=info_timeout_seconds)

    m = re.search(r"TCOUNT:(\d+)", txt)
    if m:
        return int(m.group(1)) > 0

    if "CINFO:" in txt or "TINFO:" in txt:
        return True

    drive_letter = _parse_drive_letter(disc_spec, configured_drive_letter)
    if timed_out and _drive_has_media(drive_letter):
        return True

    return False


def wait_for_disc(
    makemkv_cmd: str,
    disc_spec: str,
    poll_seconds: int = 3,
    configured_drive_letter: Optional[str] = None,
    max_wait_seconds: int = 0,
) -> bool:
    t0 = time.time()
    while True:
        if disc_present(makemkv_cmd, disc_spec, configured_drive_letter=configured_drive_letter):
            return True
        if max_wait_seconds and (time.time() - t0) > max_wait_seconds:
            return False
        time.sleep(poll_seconds)


def wait_for_disc_removed(
    makemkv_cmd: str,
    disc_spec: str,
    poll_seconds: int = 2,
    timeout_seconds: int = 0,
    configured_drive_letter: Optional[str] = None,
) -> bool:
    t0 = time.time()
    while True:
        if not disc_present(makemkv_cmd, disc_spec, configured_drive_letter=configured_drive_letter):
            return True
        if timeout_seconds and (time.time() - t0) > timeout_seconds:
            return False
        time.sleep(poll_seconds)


def rip_disc_all_titles(
    makemkv_cmd: str,
    disc_spec: str,
    out_dir: Path,
    min_length_seconds: int = 600,
) -> tuple[int, str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [makemkv_cmd, "-r", "mkv", disc_spec, "all", str(out_dir), f"--minlength={int(min_length_seconds)}"]
    p = _run(cmd)
    return p.returncode, p.stdout, p.stderr


def try_eject(
    drive_letter: str,
    makemkv_cmd: Optional[str] = None,
    disc_spec: Optional[str] = None,
) -> bool:
    """
    Returns True if COM eject command appears successful.
    """
    # Keep optional MakeMKV eject attempt as a first pass.
    if makemkv_cmd and disc_spec:
        try:
            _run([makemkv_cmd, "-r", "eject", disc_spec], timeout=30)
        except Exception:
            pass

    try:
        ps = (
            "(New-Object -ComObject Shell.Application)"
            ".NameSpace(17)"
            f".ParseName('{drive_letter}')"
            ".InvokeVerb('Eject')"
        )
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return p.returncode == 0
    except Exception:
        return False
