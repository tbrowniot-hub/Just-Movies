from __future__ import annotations
import csv, json, re
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

IMDB_RE = re.compile(r"(tt\d{7,8})")

def extract_imdb_id(url: str | None) -> Optional[str]:
    if not url:
        return None
    m = IMDB_RE.search(url)
    return m.group(1) if m else None

def normalize_barcode(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return None
    # CLZ export sometimes comes through as float-like e.g. 85392118823.0
    if s.endswith(".0") and s.replace(".","",1).isdigit():
        s = s[:-2]
    digits = re.sub(r"\D", "", s)
    return digits if digits else None

def normalize_index(val) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    # allow "123" or "123.0"
    if s.endswith(".0") and s.replace(".","",1).isdigit():
        s = s[:-2]
    return int(s) if s.isdigit() else None

@dataclass
class MovieRow:
    clz_index: int | None
    title: str
    year: int | None
    imdb_id: str | None
    barcode: str | None
    edition: str | None
    format: str | None

def iter_movies_from_clz(csv_path: Path) -> Iterable[MovieRow]:
    """
    Movies-only: expects CLZ export with at least:
      Title, Release Year, IMDb Url, Barcode, Format, Edition, Index
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("Title") or "").strip()
            if not title:
                continue
            year_raw = (row.get("Release Year") or "").strip()
            year = int(float(year_raw)) if year_raw and year_raw.lower() != "nan" else None
            imdb_id = extract_imdb_id(row.get("IMDb Url"))
            barcode = normalize_barcode(row.get("Barcode"))
            edition = (row.get("Edition") or "").strip() or None
            fmt = (row.get("Format") or "").strip() or None
            clz_idx = normalize_index(row.get("Index"))
            yield MovieRow(clz_index=clz_idx, title=title, year=year, imdb_id=imdb_id, barcode=barcode, edition=edition, format=fmt)

def build_index(csv_path: str, out_path: str) -> dict:
    p = Path(csv_path)
    movies = list(iter_movies_from_clz(p))

    by_imdb = {m.imdb_id: asdict(m) for m in movies if m.imdb_id}

    by_barcode: dict[str, list[dict]] = {}
    for m in movies:
        if m.barcode:
            by_barcode.setdefault(m.barcode, []).append(asdict(m))

    # Simple search list (for UI)
    search = []
    for m in movies:
        search.append({
            "clz_index": m.clz_index,
            "title": m.title,
            "year": m.year,
            "imdb_id": m.imdb_id,
            "barcode": m.barcode,
            "edition": m.edition,
            "format": m.format,
            "search_key": f"{(m.title or '').lower()} {m.year or ''} {m.imdb_id or ''} {m.barcode or ''} {m.clz_index or ''}".strip()
        })

    idx = {
        "schema_version": "movie_index_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "by_imdb": by_imdb,
        "by_barcode": by_barcode,
        "search": search,
        "items": search,
    }
    Path(out_path).write_text(json.dumps(idx, indent=2), encoding="utf-8")
    return idx

def load_index(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
