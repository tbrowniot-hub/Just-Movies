from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from MovieRipper import __version__
from MovieRipper.clz_index import build_index
from MovieRipper.config import CONFIG_NOT_FOUND_MESSAGE, normalize_config, resolve_path_setting, validate_config
from MovieRipper.logging_setup import configure_logging
from MovieRipper.watcher import load_queue, run_queue


def _job_folder_preview(queue_path: str, staging_root: str) -> str | None:
    try:
        queue = load_queue(queue_path)
    except Exception:
        return None
    if not queue:
        return None

    item = queue[0]
    clz_index = item.get("clz_index")
    title = item.get("title") or "Unknown Title"
    if clz_index is None:
        return None
    folder_name = f"{int(clz_index)}_{title}_<timestamp>"
    from MovieRipper.pipeline import safe_name

    return str(Path(staging_root) / safe_name(folder_name))


def _load_config_from_path(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    report = validate_config(cfg)
    return report["normalized_config"]


class RunState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.status: dict = {"running": False, "step": "idle"}
        self.logger, self.ring, _ = configure_logging(None, logger_name="movieripper.web")


STATE = RunState()
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class QueueSaveRequest(BaseModel):
    items: list[dict]
    out_path: str = "MovieRipper/movie_queue.json"


class ConfigSaveRequest(BaseModel):
    config_json: dict
    path: str = "config.json"


class ConfigValidateRequest(BaseModel):
    config_json: dict


class ConfigLoadRequest(BaseModel):
    path: str = "config.json"


class IndexLoadRequest(BaseModel):
    path: str = "MovieRipper/movie_index.json"
    eligible_only: bool = True


class RunPathCheckRequest(BaseModel):
    queue_path: str = "MovieRipper/movie_queue.json"
    config_path: str = "config.json"
    index_path: str = "MovieRipper/movie_index.json"


def create_app() -> FastAPI:
    app = FastAPI(title="MovieRipper Web")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return TEMPLATES.TemplateResponse(request, "home.html", {})

    @app.get("/import", response_class=HTMLResponse)
    def import_page(request: Request):
        return TEMPLATES.TemplateResponse(request, "import.html", {})

    @app.get("/queue", response_class=HTMLResponse)
    def queue_page(request: Request):
        return TEMPLATES.TemplateResponse(request, "queue.html", {})

    @app.get("/run", response_class=HTMLResponse)
    def run_page(request: Request):
        return TEMPLATES.TemplateResponse(request, "run.html", {})

    @app.get("/config", response_class=HTMLResponse)
    def config_page(request: Request):
        return TEMPLATES.TemplateResponse(request, "config.html", {})

    @app.get("/api/v1/version")
    def api_version():
        return {"app_version": __version__, "api_version": "v1"}

    @app.get("/api/v1/status")
    def api_status():
        with STATE.lock:
            return dict(STATE.status)

    @app.get("/api/v1/logs")
    def api_logs(tail: int = 200):
        return {"lines": STATE.ring.tail(tail)}

    @app.post("/api/v1/import")
    async def api_import(csv_file: UploadFile = File(...), out_path: str = Form("MovieRipper/movie_index.json")):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(await csv_file.read())
            temp_path = Path(tmp.name)
        try:
            index = build_index(str(temp_path), out_path)
        finally:
            temp_path.unlink(missing_ok=True)
        rows = index.get("search", [])
        eligible = [r for r in rows if r.get("imdb_id") and r.get("clz_index") is not None]
        return {
            "out_path": out_path,
            "total_rows": len(rows),
            "eligible": len(eligible),
            "missing_imdb_id": len([r for r in rows if not r.get("imdb_id")]),
            "missing_clz_index": len([r for r in rows if r.get("clz_index") is None]),
        }

    @app.post("/api/v1/queue/save")
    def api_queue_save(req: QueueSaveRequest):
        seen: set[int] = set()
        deduped: list[dict] = []
        for item in req.items:
            idx = int(item["clz_index"])
            if idx in seen:
                continue
            seen.add(idx)
            deduped.append(item)
        payload = {"items": deduped}
        path = Path(req.out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"saved": len(deduped), "out_path": str(path)}

    @app.post("/api/v1/run/start")
    def api_run_start(queue_path: str = Form(...), config_path: str | None = Form(None)):
        with STATE.lock:
            if STATE.thread and STATE.thread.is_alive():
                raise HTTPException(status_code=409, detail="Queue run already in progress")

            resolved_config_path = config_path or "config.json"
            try:
                cfg = _load_config_from_path(resolved_config_path)
            except FileNotFoundError:
                raise HTTPException(status_code=400, detail=CONFIG_NOT_FOUND_MESSAGE)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON in config: {exc}") from exc

            report = validate_config(cfg)
            if not report["valid"]:
                raise HTTPException(status_code=400, detail="; ".join(report["errors"]))

            STATE.logger, STATE.ring, _ = configure_logging(cfg.get("log_dir"), logger_name="movieripper")
            STATE.stop_event.clear()
            STATE.status = {"running": True, "step": "starting", "queue_path": queue_path}

            def _status_callback(update: dict) -> None:
                with STATE.lock:
                    STATE.status.update(update)

            t = threading.Thread(
                target=run_queue,
                kwargs={
                    "cfg": cfg,
                    "queue_path": queue_path,
                    "status_callback": _status_callback,
                    "stop_event": STATE.stop_event,
                },
                daemon=True,
            )
            STATE.thread = t
            t.start()
        return {"started": True}

    @app.post("/api/v1/run/paths")
    def api_run_paths(req: RunPathCheckRequest):
        queue_path = Path(req.queue_path)
        config_path = Path(req.config_path)
        index_path = Path(req.index_path)

        config_exists = config_path.exists()
        config_valid = False
        config_errors: list[str] = []
        config_warnings: list[str] = []
        staging_root = None
        final_root = None

        if config_exists:
            try:
                config_json = json.loads(config_path.read_text(encoding="utf-8"))
                report = validate_config(config_json)
                config_valid = bool(report["valid"])
                config_errors = report["errors"]
                config_warnings = report["warnings"]
                staging_root = report["resolved"].get("rips_staging_root")
                final_root = report["resolved"].get("final_movies_root")
            except json.JSONDecodeError as exc:
                config_errors = [f"Invalid JSON in config file: {exc}"]

        return {
            "queue_path": str(queue_path),
            "queue_exists": queue_path.exists(),
            "config_path": str(config_path),
            "config_exists": config_exists,
            "config_valid": config_valid,
            "config_errors": config_errors,
            "config_warnings": config_warnings,
            "staging_root": staging_root,
            "final_root": final_root,
            "job_folder_preview": _job_folder_preview(str(queue_path), staging_root) if staging_root and queue_path.exists() else None,
            "index_path": str(index_path),
            "index_exists": index_path.exists(),
        }

    @app.post("/api/v1/run/stop")
    def api_run_stop():
        STATE.stop_event.set()
        with STATE.lock:
            STATE.status.update({"running": False, "step": "stopped"})
        return {"stopping": True}

    @app.post("/api/v1/config/save")
    def api_config_save(req: ConfigSaveRequest):
        out = Path(req.path)
        out.parent.mkdir(parents=True, exist_ok=True)

        normalized = normalize_config(req.config_json)
        for key in ("rips_staging_root", "final_movies_root"):
            resolved = resolve_path_setting(req.config_json, key)
            if resolved:
                normalized[key] = resolved

        out.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        return {"saved": str(out), "config_json": normalized}

    @app.post("/api/v1/config/load")
    def api_config_load(req: ConfigLoadRequest):
        path = Path(req.path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Config file not found: {path}")
        try:
            config_json = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in config file: {exc}") from exc

        report = validate_config(config_json)
        return {"path": str(path), "config_json": report["normalized_config"], "validation": report}

    @app.post("/api/v1/config/validate")
    def api_config_validate(req: ConfigValidateRequest):
        report = validate_config(req.config_json)
        return report

    @app.post("/api/v1/index/load")
    def api_index_load(req: IndexLoadRequest):
        path = Path(req.path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Index file not found: {path}")

        try:
            index_data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON in index file: {exc}") from exc

        source_items = index_data.get("items")
        if source_items is None:
            source_items = index_data.get("search")

        if not isinstance(source_items, list):
            raise HTTPException(status_code=422, detail="Index JSON must include list key 'items' or 'search'.")

        total = len(source_items)
        missing_imdb = len([item for item in source_items if not item.get("imdb_id")])

        if req.eligible_only:
            source_items = [item for item in source_items if item.get("imdb_id") and item.get("clz_index") is not None]

        return {
            "path": str(path),
            "total": total,
            "eligible_only": req.eligible_only,
            "items": source_items,
            "missing_imdb_count": missing_imdb,
            "loaded_count": len(source_items),
        }

    return app
