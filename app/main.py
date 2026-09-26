"""HTTP API + web widget.  Run:  uv run uvicorn app.main:app --reload"""

import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import build_agent
from app.config import BASE_DIR, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()
STATIC_DIR = BASE_DIR / "static"


class RateLimiter:
    """Allow `limit` requests per client per minute (in memory - fine for a single server)."""

    def __init__(self, limit: int):
        self._limit = limit
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent, app.state.kb, app.state.db = build_agent(settings)
    if not app.state.kb.sources():
        logging.warning("Knowledge base is empty - run: uv run python -m app.ingest")
    yield


app = FastAPI(title=f"{settings.bot_name} API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["GET", "POST"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
limiter = RateLimiter(settings.rate_limit_per_minute)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=settings.max_message_chars)
    session_id: str | None = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    sources: list[str]


@app.get("/")
def demo_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "documents": len(app.state.kb.sources())}


@app.get("/api/config")
def widget_config():
    return {"bot_name": settings.bot_name, "business_name": settings.business_name, "greeting": settings.greeting}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many messages. Please wait a minute.")
    session_id = body.session_id or uuid.uuid4().hex
    result = app.state.agent.reply(session_id, body.message.strip())
    return ChatResponse(session_id=session_id, reply=result.text, sources=result.sources)


@app.get("/api/tickets")
def tickets(x_admin_token: str = Header(default="")):
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return app.state.db.list_tickets()
