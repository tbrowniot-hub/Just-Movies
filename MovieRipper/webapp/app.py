from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from MovieRipper.clz_index import build_index
from MovieRipper.config import CONFIG_NOT_FOUND_MESSAGE, load_config
from MovieRipper.logging_setup import RingBufferHandler, configure_logging
from MovieRipper.watcher import run_queue


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


def create_app() -> FastAPI:
    app = FastAPI(title="MovieRipper Web")
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return TEMPLATES.TemplateResponse("home.html", {"request": request})

    @app.get("/import", response_class=HTMLResponse)
    def import_page(request: Request):
        return TEMPLATES.TemplateResponse("import.html", {"request": request})

    @app.get("/queue", response_class=HTMLResponse)
    def queue_page(request: Request):
        return TEMPLATES.TemplateResponse("queue.html", {"request": request})

    @app.get("/run", response_class=HTMLResponse)
    def run_page(request: Request):
        return TEMPLATES.TemplateResponse("run.html", {"request": request})

    @app.get("/config", response_class=HTMLResponse)
    def config_page(request: Request):
        return TEMPLATES.TemplateResponse("config.html", {"request": request})

    @app.get("/api/status")
    def api_status():
        return STATE.status

    @app.get("/api/logs")
    def api_logs(tail: int = 200):
        return {"lines": STATE.ring.tail(tail)}

    @app.post("/api/import")
    async def api_import(csv_file: UploadFile = File(...), out_path: str = Form("MovieRipper/movie_index.json")):
        temp_path = Path("/tmp") / (csv_file.filename or "masterexport.csv")
        temp_path.write_bytes(await csv_file.read())
        index = build_index(str(temp_path), out_path)
        rows = index.get("search", [])
        eligible = [r for r in rows if r.get("imdb_id") and r.get("clz_index") is not None]
        return {
            "out_path": out_path,
            "total_rows": len(rows),
            "eligible": len(eligible),
            "missing_imdb_id": len([r for r in rows if not r.get("imdb_id")]),
            "missing_clz_index": len([r for r in rows if r.get("clz_index") is None]),
        }

    @app.post("/api/queue/save")
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

    @app.post("/api/run/start")
    def api_run_start(queue_path: str = Form(...), config_path: str | None = Form(None)):
        with STATE.lock:
            if STATE.thread and STATE.thread.is_alive():
                raise HTTPException(status_code=409, detail="Queue run already in progress")

            try:
                cfg, _, _ = load_config(config_path)
            except FileNotFoundError:
                raise HTTPException(status_code=400, detail=CONFIG_NOT_FOUND_MESSAGE)

            STATE.logger, STATE.ring, _ = configure_logging(cfg.get("log_dir"), logger_name="movieripper")
            STATE.stop_event.clear()
            STATE.status = {"running": True, "step": "starting", "queue_path": queue_path}

            def _status_callback(update: dict) -> None:
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

    @app.post("/api/run/stop")
    def api_run_stop():
        STATE.stop_event.set()
        STATE.status.update({"running": False, "step": "stopped"})
        return {"stopping": True}

    @app.post("/api/config/save")
    def api_config_save(req: ConfigSaveRequest):
        out = Path(req.path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(req.config_json, indent=2), encoding="utf-8")
        return {"saved": str(out)}

    @app.post("/api/config/validate")
    def api_config_validate(req: ConfigValidateRequest):
        config_json = req.config_json
        checks = {
            "rip_prep_root_exists": Path(config_json.get("rip_prep_root", "")).exists(),
            "rip_staging_root_exists": Path(config_json.get("rip_staging_root", "")).exists(),
            "makemkv_exists": Path(config_json.get("makemkv_cmd", "")).exists(),
            "staging_parent_writable": Path(config_json.get("rip_staging_root", ".")).parent.exists(),
        }
        return {"valid": all(checks.values()), "checks": checks}

    return app
