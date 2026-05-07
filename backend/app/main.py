from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings
from backend.app.contracts import ChatRequest, ChatResponse
from backend.app.db import Database, init_schema
from backend.app.logging_utils import configure_logging
from backend.app.openrouter import OpenRouterClient
from backend.app.rag import RagService


settings = get_settings()
configure_logging(settings.log_level)
db = Database(settings)
openrouter = OpenRouterClient(settings)
rag = RagService(settings, db, openrouter)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    await init_schema(db)
    await rag.index_documents()
    yield
    await openrouter.close()
    await db.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

frontend_dir = Path("/app/frontend")
if not frontend_dir.exists():
    frontend_dir = Path("frontend")

if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервиса HelpBot"},
    )


@app.get("/")
async def index() -> FileResponse:
    index_path = frontend_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend is not available")
    return FileResponse(index_path)


@app.get("/health")
async def health() -> dict[str, str]:
    async with db.acquire() as conn:
        await conn.fetchval("SELECT 1")
        await conn.fetchval("SELECT to_regclass('public.kb_chunks')")
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    message = payload.message.strip()
    if len(message) > settings.max_message_chars:
        raise HTTPException(status_code=422, detail="Сообщение слишком длинное")
    return await rag.answer(message)
