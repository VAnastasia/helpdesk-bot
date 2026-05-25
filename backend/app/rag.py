from __future__ import annotations

import asyncio
import logging
import re

from asyncpg import Record
from asyncpg.exceptions import DataError
from langchain_core.prompts import ChatPromptTemplate

from backend.app.config import Settings
from backend.app.contracts import ChatResponse, Source
from backend.app.db import Database
from backend.app.documents import KnowledgeChunk, load_knowledge_chunks
from backend.app.logging_utils import sanitize_for_log
from backend.app.openrouter import OpenRouterClient, OpenRouterError


logger = logging.getLogger(__name__)

FALLBACK_ANSWER = (
    "К сожалению, в базе знаний нет точной информации по этому вопросу. "
    "Попробуйте сформулировать вопрос иначе или обратитесь в IT: incident@company.ru."
)

SOURCE_BLOCK_RE = re.compile(r"\s*(?:Источник:\s*)?\[Документ:[^\]]+\][.!?]?\s*$")


class RagService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        openrouter: OpenRouterClient,
    ):
        self.settings = settings
        self.db = db
        self.openrouter = openrouter
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", _load_system_prompt(settings)),
                (
                    "user",
                    "Вопрос сотрудника:\n{question}\n\n"
                    "Релевантный контекст из базы знаний:\n{context}\n\n"
                    "Ответь строго по контексту. Если точного ответа нет, верни fallback.",
                ),
            ]
        )

    async def index_documents(self) -> None:
        chunks = await asyncio.to_thread(load_knowledge_chunks, self.settings.docs_dir)
        if not chunks:
            logger.warning("No knowledge base chunks found in %s", self.settings.docs_dir)
            return

        logger.info("Indexing %s knowledge chunks", len(chunks))
        async with self.db.acquire() as conn:
            existing = await conn.fetch(
                "SELECT id, content_hash FROM kb_chunks WHERE id = ANY($1::text[])",
                [chunk.id for chunk in chunks],
            )
            unchanged = {row["id"] for row in existing if row["content_hash"]}

        to_embed = [chunk for chunk in chunks if chunk.id not in unchanged]
        for batch in _batches(to_embed, 32):
            embeddings = await self.openrouter.embed([chunk.content for chunk in batch])
            await self._upsert_chunks(batch, embeddings)

        current_ids = [chunk.id for chunk in chunks]
        async with self.db.acquire() as conn:
            await conn.execute(
                "DELETE FROM kb_chunks WHERE NOT (id = ANY($1::text[]))",
                current_ids,
            )
        logger.info("Knowledge base indexing complete")

    async def answer(self, message: str) -> ChatResponse:
        clean_message = message.strip()

        try:
            question_embedding = (await self.openrouter.embed([clean_message]))[0]
            rows = await self._search(question_embedding)
        except (OpenRouterError, DataError):
            logger.exception("RAG retrieval failure for message=%s", sanitize_for_log(clean_message))
            return _fallback()

        relevant = [
            row for row in rows if row["similarity"] >= self.settings.rag_similarity_threshold
        ]
        if not relevant:
            return _fallback()

        context, sources = _format_context(relevant, self.settings.max_context_chars)
        messages = self.prompt_template.format_messages(
            question=clean_message,
            context=context,
        )
        openrouter_messages = [
            {"role": _openrouter_role(message.type), "content": str(message.content)}
            for message in messages
        ]

        try:
            answer = await self.openrouter.chat(openrouter_messages)
        except OpenRouterError:
            logger.exception("OpenRouter chat failure for message=%s", sanitize_for_log(clean_message))
            return _fallback()

        answer = _strip_trailing_source(answer)
        return ChatResponse(answer=answer, sources=sources, fallback=False)

    async def _upsert_chunks(
        self, chunks: list[KnowledgeChunk], embeddings: list[list[float]]
    ) -> None:
        async with self.db.acquire() as conn:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                await conn.execute(
                    """
                    INSERT INTO kb_chunks (
                        id, content, document, section, filename, content_hash, embedding, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7::vector, now())
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        document = EXCLUDED.document,
                        section = EXCLUDED.section,
                        filename = EXCLUDED.filename,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        updated_at = now()
                    """,
                    chunk.id,
                    chunk.content,
                    chunk.document,
                    chunk.section,
                    chunk.filename,
                    chunk.content_hash,
                    _vector_literal(embedding),
                )

    async def _search(self, embedding: list[float]) -> list[Record]:
        async with self.db.acquire() as conn:
            return await conn.fetch(
                """
                SELECT content, document, section, filename,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM kb_chunks
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                _vector_literal(embedding),
                self.settings.rag_top_k,
            )


def _load_system_prompt(settings: Settings) -> str:
    if settings.prompt_path.exists():
        return settings.prompt_path.read_text(encoding="utf-8")
    fallback_path = settings.prompt_path.with_name("propmpt.txt")
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8")
    return (
        "Ты HelpBot, ИИ-ассистент внутренней IT-поддержки. "
        "Отвечай только по предоставленному контексту и всегда указывай источник."
    )


def _format_context(rows: list[Record], max_chars: int) -> tuple[str, list[Source]]:
    parts: list[str] = []
    sources: list[Source] = []
    seen_sources: set[tuple[str, str]] = set()
    used = 0

    for row in rows:
        source = Source(document=row["document"], section=row["section"])
        source_key = (source.document, source.section)
        if source_key not in seen_sources:
            sources.append(source)
            seen_sources.add(source_key)

        label = _source_label(source)
        part = f"{label}\n{row['content']}"
        if used + len(part) > max_chars:
            break
        parts.append(part)
        used += len(part)

    return "\n\n---\n\n".join(parts), sources


def _source_label(source: Source) -> str:
    return f"[Документ: {source.document}, раздел: {source.section}]"


def _answer_has_source(answer: str, sources: list[Source]) -> bool:
    if "[Документ:" not in answer:
        return False
    return any(source.document in answer for source in sources)


def _strip_trailing_source(answer: str) -> str:
    answer = SOURCE_BLOCK_RE.sub("", answer.rstrip()).rstrip()
    lines = answer.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return ""

    last_line = lines[-1].strip()
    if _is_source_line(last_line):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines).rstrip()


def _is_source_line(line: str) -> bool:
    normalized = line.strip()
    if normalized.startswith("Источник:"):
        normalized = normalized.removeprefix("Источник:").strip()
    return normalized.startswith("[Документ:") and normalized.endswith("]")


def _fallback() -> ChatResponse:
    return ChatResponse(answer=FALLBACK_ANSWER, sources=[], fallback=True)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _openrouter_role(langchain_role: str) -> str:
    if langchain_role == "human":
        return "user"
    if langchain_role == "ai":
        return "assistant"
    return langchain_role


def _batches(items: list[KnowledgeChunk], size: int) -> list[list[KnowledgeChunk]]:
    return [items[index : index + size] for index in range(0, len(items), size)]
