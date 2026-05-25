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
        chunks.extend(_load_markdown_file(path))
    return chunks


def _load_markdown_file(path: Path) -> list[KnowledgeChunk]:
    raw = path.read_text(encoding="utf-8")
    content = raw.strip()
    document_title = _document_title(raw, path)
    sections = _sections(raw)

    if not sections:
        return [
            _build_chunk(
                path=path,
                document=document_title,
                section="Весь документ",
                content=content,
                section_index=0,
            )
        ]

    return [
        _build_chunk(
            path=path,
            document=document_title,
            section=section,
            content=section_content,
            section_index=index,
        )
        for index, (section, section_content) in enumerate(sections, start=1)
    ]


def _build_chunk(
    path: Path,
    document: str,
    section: str,
    content: str,
    section_index: int,
) -> KnowledgeChunk:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    chunk_id = hashlib.sha256(
        f"{path.name}:{section_index}:{section}:{content_hash}".encode("utf-8")
    ).hexdigest()
    return KnowledgeChunk(
        id=chunk_id,
        content=content,
        document=document,
        section=section,
        filename=path.name,
        content_hash=content_hash,
    )


def _document_title(raw: str, path: Path) -> str:
    for line in raw.splitlines():
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2).strip()
    return path.stem


def _sections(raw: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_section: str | None = None
    current_lines: list[str] = []

    for line in raw.splitlines():
        match = HEADING_RE.match(line)
        if match and len(match.group(1)) == 2:
            if current_section is not None:
                sections.append((current_section, current_lines))
            current_section = match.group(2).strip()
            current_lines = [line]
            continue

        if current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections.append((current_section, current_lines))

    chunks: list[tuple[str, str]] = []
    for section, lines in sections:
        content = "\n".join(lines).strip()
        if content:
            chunks.append((section, content))
    return chunks
