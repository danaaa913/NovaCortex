"""FastAPI adapter for the local RAG engine and its bundled web interface."""

import asyncio
import hmac
import os
from pathlib import Path
from typing import Optional

from .config import HackathonConfig
from .pipeline import HackathonRAG


WEB_DIR = Path(__file__).with_name("web")
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_engine: Optional[HackathonRAG] = None


def validate_bind_security(host: str, token: str) -> None:
    """Refuse an unauthenticated network deployment by default."""
    if host.strip().casefold() not in LOOPBACK_HOSTS and not token.strip():
        raise RuntimeError(
            "HACKATHON_API_TOKEN is required when the API is exposed beyond localhost."
        )


def _rag() -> HackathonRAG:
    global _engine
    if _engine is None:
        _engine = HackathonRAG(HackathonConfig())
    return _engine


def create_app():
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
        from fastapi.concurrency import run_in_threadpool
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI UI requires fastapi and uvicorn from hackathon_requirements.txt"
        ) from exc

    api_token = os.getenv("HACKATHON_API_TOKEN", "").strip()
    max_concurrent = max(1, int(os.getenv("HACKATHON_MAX_CONCURRENT_QUESTIONS", "1")))
    generation_slots = asyncio.Semaphore(max_concurrent)

    class AskRequest(BaseModel):
        question: str = Field(min_length=1, max_length=4000)
        sources: list[str] = Field(default_factory=list, max_length=30)

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if not api_token:
            return
        expected = f"Bearer {api_token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Missing or invalid access token")

    app = FastAPI(
        title="NovaCortex Local Government Service Assistant",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/health")
    def health():
        engine = _rag()
        return {
            "status": "ready" if engine.store.manifest_path.exists() else "index_missing",
            "index_ready": engine.store.manifest_path.exists(),
            "chat_model": engine.config.chat_model,
            "embedding_model": engine.config.embedding_model,
            "local_processing": True,
            "authentication_required": bool(api_token),
        }

    @app.get("/api/sources", dependencies=[Depends(authorize)])
    def sources():
        try:
            return {"sources": _rag().available_sources()}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/ask", dependencies=[Depends(authorize)])
    async def ask(payload: AskRequest):
        requested_sources = list(dict.fromkeys(source.strip() for source in payload.sources if source.strip()))
        try:
            available = set(await run_in_threadpool(_rag().available_sources))
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        unknown = sorted(set(requested_sources) - available)
        if unknown:
            raise HTTPException(status_code=400, detail={"unknown_sources": unknown})
        async with generation_slots:
            try:
                result = await run_in_threadpool(
                    lambda: _rag().ask(payload.question, source_scope=requested_sources)
                )
            except (RuntimeError, ValueError, FileNotFoundError) as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return result.to_dict()

    return app
