import os
import threading
import logging
import uvicorn
from fastapi import FastAPI, Request, Form, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

logger = logging.getLogger(__name__)


class RemoteServer:
    """FastAPI-based remote control server running in a background thread."""

    def __init__(self, bgm_player, announcement_manager,
                 schedule_manager, auth_manager, settings: dict,
                 save_settings_fn=None):
        self._bgm = bgm_player
        self._ann_manager = announcement_manager
        self._sched_manager = schedule_manager
        self._auth = auth_manager
        self._settings = settings
        self._save_settings = save_settings_fn
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None

        self.app = FastAPI(title="ITN Fitness Broadcast Control")
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        self._templates = Jinja2Templates(directory=templates_dir)
        self._setup_routes()

    def _require_auth(self, session_token: Optional[str]) -> bool:
        if not self._settings.get("remote", {}).get("require_auth", True):
            return True
        if not session_token:
            return False
        return self._auth.verify_session(session_token)

    def _setup_routes(self):
        app = self.app

        @app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request,
                            session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                return RedirectResponse("/login")

            next_ann = self._sched_manager.get_next_announcement()
            return self._templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "bgm_state": self._bgm.state.value,
                    "bgm_volume": self._bgm.volume,
                    "bgm_title": self._bgm.title,
                    "categories": self._ann_manager.categories,
                    "today_schedule": self._sched_manager.get_today_schedule(),
                    "next_announcement": next_ann,
                    "show_login": False,
                },
            )

        @app.get("/login", response_class=HTMLResponse)
        async def login_page(request: Request):
            return self._templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "show_login": True},
            )

        @app.post("/login")
        async def login(password: str = Form(...)):
            if not self._auth.is_configured:
                hash_str = self._auth.set_password(password)
                if self._save_settings:
                    self._settings.setdefault("remote", {})["password_hash"] = hash_str
                    self._save_settings()
            elif not self._auth.verify_password(password):
                raise HTTPException(401, "Invalid password")

            token = self._auth.create_session()
            response = RedirectResponse("/", status_code=303)
            response.set_cookie("session", token, httponly=True)
            return response

        @app.post("/api/bgm/play")
        async def bgm_play(url: str = Form(None),
                           session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            play_url = url or self._settings.get("bgm", {}).get("default_url", "")
            if not play_url:
                raise HTTPException(400, "No URL provided")
            self._bgm.play(play_url)
            return {"status": "ok"}

        @app.post("/api/bgm/stop")
        async def bgm_stop(session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            self._bgm.stop()
            return {"status": "ok"}

        @app.post("/api/bgm/pause")
        async def bgm_pause(session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            self._bgm.pause()
            return {"status": "ok"}

        @app.post("/api/bgm/volume")
        async def bgm_volume(volume: int = Form(...),
                             session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            self._bgm.volume = volume
            return {"status": "ok", "volume": self._bgm.volume}

        @app.post("/api/announce")
        async def announce(category: str = Form(...),
                           item_id: str = Form(...),
                           session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            success = self._ann_manager.broadcast(category, item_id)
            return {"status": "ok" if success else "busy"}

        @app.post("/api/emergency")
        async def emergency(item_id: str = Form(...),
                            session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            self._ann_manager.broadcast_emergency(item_id)
            return {"status": "ok"}

        @app.get("/api/status")
        async def status(session: Optional[str] = Cookie(None)):
            if not self._require_auth(session):
                raise HTTPException(401)
            next_ann = self._sched_manager.get_next_announcement()
            return {
                "bgm_state": self._bgm.state.value,
                "bgm_volume": self._bgm.volume,
                "bgm_title": self._bgm.title,
                "broadcasting": self._ann_manager.is_broadcasting,
                "next_announcement": next_ann,
            }

    def start(self):
        host = self._settings.get("remote", {}).get("host", "0.0.0.0")
        port = self._settings.get("remote", {}).get("port", 8585)

        config = uvicorn.Config(
            self.app, host=host, port=port, log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        logger.info(f"Remote server started on {host}:{port}")

    def stop(self):
        if self._server:
            self._server.should_exit = True
