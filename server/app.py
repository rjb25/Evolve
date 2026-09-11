from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server import session as session_mod

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/Evolution")
@app.get("/Evolution/")
def index():
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/Evolution/api/health")
def health():
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "sessions": session_mod.session_count(),
        "max_sessions": session_mod.MAX_SESSIONS,
    }


@app.get("/Evolution/api/snapshot")
async def debug_snapshot(sid: str | None = None):
    snap = await session_mod.snapshot_by_sid(sid)
    if snap is None:
        return JSONResponse({"error": "no session"}, status_code=404)
    return snap


@app.websocket("/Evolution/ws")
async def ws_endpoint(ws: WebSocket):
    origin = ws.headers.get("origin")
    if origin not in session_mod.ALLOWED_WS_ORIGINS:
        await session_mod.reject_websocket(ws, 1008)
        return
    await session_mod.run_session(ws)


app.mount("/Evolution/static", StaticFiles(directory=WEB_ROOT), name="static")
