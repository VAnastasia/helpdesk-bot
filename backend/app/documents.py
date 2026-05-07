from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    content: str
    document: str
    section: str
    filename: str
    content_hash: str


def load_knowledge_chunks(docs_dir: Path) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.append(_load_markdown_file(path))
    return chunks


def _load_markdown_file(path: Path) -> KnowledgeChunk:
    raw = path.read_text(encoding="utf-8")
    content = raw.strip()
    document_title = _document_title(raw, path)
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    chunk_id = hashlib.sha256(f"{path.name}:{content_hash}".encode("utf-8")).hexdigest()
    return KnowledgeChunk(
        id=chunk_id,
        content=content,
        document=document_title,
        section="Весь документ",
        filename=path.name,
        content_hash=content_hash,
    )


def _document_title(raw: str, path: Path) -> str:
    for line in raw.splitlines():
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    return path.stem
