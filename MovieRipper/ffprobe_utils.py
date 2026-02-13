
from __future__ import annotations
import json, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class MediaInfo:
    path: str
    duration: float
    size_bytes: int
    video_codec: Optional[str]
    width: Optional[int]
    height: Optional[int]
    audio_codecs: list[str]
    audio_tracks: int
    subtitle_tracks: int

def run_ffprobe(ffprobe_cmd: str, file_path: str) -> dict:
    cmd = [
        ffprobe_cmd, "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {file_path}:\n{p.stderr}")
    return json.loads(p.stdout)

def parse_media_info(file_path: str, ffprobe_cmd: str = "ffprobe") -> MediaInfo:
    fp = Path(file_path)
    data = run_ffprobe(ffprobe_cmd, str(fp))
    fmt = data.get("format", {})
    dur = float(fmt.get("duration") or 0.0)
    size = int(fmt.get("size") or fp.stat().st_size)
    vcodec = None; w=None; h=None
    acodecs=[]
    a_tracks=0
    s_tracks=0
    for st in data.get("streams", []) or []:
        t = st.get("codec_type")
        if t == "video" and vcodec is None:
            vcodec = st.get("codec_name")
            w = st.get("width")
            h = st.get("height")
        elif t == "audio":
            a_tracks += 1
            c = st.get("codec_name")
            if c: acodecs.append(c.lower())
        elif t == "subtitle":
            s_tracks += 1
    return MediaInfo(
        path=str(fp),
        duration=dur,
        size_bytes=size,
        video_codec=vcodec.lower() if vcodec else None,
        width=int(w) if w else None,
        height=int(h) if h else None,
        audio_codecs=acodecs,
        audio_tracks=a_tracks,
        subtitle_tracks=s_tracks
    )
