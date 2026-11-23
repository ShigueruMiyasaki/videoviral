"""
API FastAPI — Dashboard de aprovação humana.

Rodar na raiz do projeto:
    uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import base64
import secrets
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routes import approval, jobs, setup
from config.settings import settings

app = FastAPI(
    title="VideoViral Approval API",
    version="0.2.0",
    description="Fila de aprovação e render pós-aprovação",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(approval.router)
app.include_router(setup.router)


def _unauthorized() -> Response:
    return Response(
        status_code=401,
        content="Autenticação necessária",
        headers={"WWW-Authenticate": 'Basic realm="VideoViral"'},
    )


@app.middleware("http")
async def require_dashboard_auth(request: Request, call_next):
    """Exige senha só quando DASHBOARD_PASSWORD está definido. /health fica aberto."""
    password = settings.dashboard_password
    if not password or request.url.path == "/health":
        return await call_next(request)

    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return _unauthorized()
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1], validate=True).decode("utf-8")
        user, _, given = decoded.partition(":")
    except (ValueError, UnicodeDecodeError):
        return _unauthorized()

    user_ok = secrets.compare_digest(user, settings.dashboard_user or "admin")
    pass_ok = secrets.compare_digest(given, password)
    if not (user_ok and pass_ok):
        return _unauthorized()
    return await call_next(request)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "videoviral-api"}


@app.get("/setup")
def setup_page():
    page = STATIC_DIR / "setup.html"
    if not page.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse({"message": "setup.html ausente"}, status_code=404)
    return FileResponse(page)


@app.get("/")
def dashboard():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"message": "Dashboard em /static — arquivo index.html ausente"},
            status_code=404,
        )
    return FileResponse(index)


@app.get("/media/{path:path}")
def serve_media(path: str) -> FileResponse:
    """Serve clipes locais para preview no dashboard."""
    file_path = (ROOT / path).resolve()
    storage = (ROOT / "storage").resolve()
    if not file_path.is_relative_to(storage):
        from fastapi import HTTPException
        raise HTTPException(403, "Acesso negado")
    if not file_path.exists():
        from fastapi import HTTPException
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(file_path)
