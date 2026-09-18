from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engine.survivor import ActError
from server import session as session_mod

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"

_PREFIX = "/evolution"


class _CanonicalEvolution:
    """Serve /evolution the same as /Evolution (any non-canonical casing)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path") or ""
            lower = path.lower()
            if lower == _PREFIX or lower.startswith(_PREFIX + "/"):
                if not path.startswith("/Evolution"):
                    scope = dict(scope)
                    canon = "/Evolution" + path[len(_PREFIX) :]
                    scope["path"] = canon
                    if "raw_path" in scope:
                        scope["raw_path"] = canon.encode("utf-8")
        await self.app(scope, receive, send)


_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app = _CanonicalEvolution(_app)


@_app.get("/Evolution")
@_app.get("/Evolution/")
def index():
    return FileResponse(WEB_ROOT / "index.html")


@_app.get("/Evolution/api/health")
def health():
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "sessions": session_mod.session_count(),
        "max_sessions": session_mod.MAX_SESSIONS,
    }


@_app.get("/Evolution/api/lobbies")
def lobbies():
    return {"lobbies": session_mod.list_lobbies()}


def _post_origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin in session_mod.ALLOWED_WS_ORIGINS:
        return True
    # Same-host POST (some browsers/proxies omit Origin).
    host = (request.headers.get("host") or "").split(":")[0].lower()
    return origin in (None, "") and host in {
        "roleplaycardgame.com",
        "127.0.0.1",
        "localhost",
    }


@_app.post("/Evolution/api/lobbies")
async def create_lobby(request: Request):
    if not _post_origin_ok(request):
        return JSONResponse({"error": "origin"}, status_code=403)
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    seed = body.get("seed")
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError):
            seed = None
    try:
        lobby = await session_mod.create_lobby(seed=seed)
    except ActError as exc:
        return JSONResponse({"error": exc.code, "detail": exc.detail}, status_code=503)
    return {"id": lobby.id, "seed": lobby.world.seed}


@_app.get("/Evolution/api/snapshot")
async def debug_snapshot(sid: str | None = None):
    snap = await session_mod.snapshot_by_sid(sid)
    if snap is None:
        return JSONResponse({"error": "no session"}, status_code=404)
    return snap


@_app.websocket("/Evolution/ws")
async def ws_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin not in session_mod.ALLOWED_WS_ORIGINS:
        await session_mod.reject_websocket(ws, 1008)
        return
    await session_mod.run_session(ws)


_app.mount("/Evolution/static", StaticFiles(directory=WEB_ROOT), name="static")
