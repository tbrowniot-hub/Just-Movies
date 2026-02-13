
from __future__ import annotations
import math, re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from .ffprobe_utils import parse_media_info, MediaInfo

ANGLE_RE = re.compile(r"angle\s*(\d+)", re.IGNORECASE)

def label_angle(path: str) -> Optional[int]:
    m = ANGLE_RE.search(Path(path).name)
    return int(m.group(1)) if m else None

def audio_score(codecs: list[str]) -> int:
    # very rough preference scoring
    score = 0
    for c in codecs:
        if "truehd" in c: score += 50
        elif "dts" in c and "hd" in c: score += 40
        elif c == "dts": score += 30
        elif c in ("eac3","ec-3"): score += 20
        elif c == "ac3": score += 15
        elif c == "aac": score += 10
        else: score += 5
    return score

def pick_keeper(mkv_paths: Iterable[str], ffprobe_cmd: str, min_minutes: float, duration_tol: float, prefer_angle_1: bool) -> MediaInfo:
    infos = [parse_media_info(p, ffprobe_cmd=ffprobe_cmd) for p in mkv_paths]
    # filter
    candidates = [i for i in infos if i.duration >= min_minutes*60]
    if not candidates:
        raise RuntimeError(f"No MKV files >= {min_minutes} minutes found.")
    # select longest duration bucket (allow tiny tolerance)
    max_dur = max(i.duration for i in candidates)
    bucket = [i for i in candidates if abs(i.duration - max_dur) <= duration_tol]
    if len(bucket) == 1:
        return bucket[0]

    # If angles are labeled and we prefer angle 1
    if prefer_angle_1:
        for i in bucket:
            ang = label_angle(i.path)
            if ang == 1:
                return i

    # Score-based selection: higher estimated bitrate + better audio + more subs (often indicates main)
    def score(i: MediaInfo) -> float:
        bitrate = (i.size_bytes / max(i.duration, 1.0))  # bytes/sec
        return (bitrate / 1_000_000.0) + (audio_score(i.audio_codecs) / 10.0) + (i.subtitle_tracks * 0.1) + (i.audio_tracks * 0.05)

    bucket_sorted = sorted(bucket, key=score, reverse=True)
    return bucket_sorted[0]
