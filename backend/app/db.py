from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import re

import asyncpg

from backend.app.config import Settings


logger = logging.getLogger(__name__)
VECTOR_TYPE_RE = re.compile(r"^vector\((\d+)\)$")


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.settings.database_url,
            min_size=1,
            max_size=5,
            command_timeout=self.settings.request_timeout_seconds,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        if self.pool is None:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as conn:
            yield conn


async def init_schema(db: Database) -> None:
    dimensions = db.settings.embedding_dimensions
    async with db.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        current_dimensions = await _current_embedding_dimensions(conn)
        if current_dimensions is not None and current_dimensions != dimensions:
            logger.warning(
                "Recreating kb_chunks because embedding dimensions changed from %s to %s",
                current_dimensions,
                dimensions,
            )
            await conn.execute("DROP TABLE IF EXISTS kb_chunks CASCADE")
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS kb_chunks (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                document TEXT NOT NULL,
                section TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding vector({dimensions}) NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_kb_chunks_document
            ON kb_chunks (document)
            """
        )
        if _can_create_hnsw_index(dimensions):
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
                ON kb_chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        else:
            await conn.execute("DROP INDEX IF EXISTS idx_kb_chunks_embedding")
            logger.warning(
                "Skipping HNSW index for %s-dimensional embeddings; pgvector HNSW "
                "supports vector dimensions up to 2000. Sequential scan will be used.",
                dimensions,
            )


async def _current_embedding_dimensions(conn: asyncpg.Connection) -> int | None:
    data_type = await conn.fetchval(
        """
        SELECT format_type(attribute.atttypid, attribute.atttypmod)
        FROM pg_attribute AS attribute
        JOIN pg_class AS class ON attribute.attrelid = class.oid
        JOIN pg_namespace AS namespace ON class.relnamespace = namespace.oid
        WHERE namespace.nspname = 'public'
          AND class.relname = 'kb_chunks'
          AND attribute.attname = 'embedding'
          AND NOT attribute.attisdropped
        """
    )
    if data_type is None:
        return None
    return _parse_vector_dimensions(data_type)


def _parse_vector_dimensions(data_type: str) -> int | None:
    match = VECTOR_TYPE_RE.match(data_type)
    if match is None:
        return None
    return int(match.group(1))


def _can_create_hnsw_index(dimensions: int) -> bool:
    return dimensions <= 2000
