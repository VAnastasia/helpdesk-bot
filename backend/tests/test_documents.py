from pathlib import Path

from backend.app.documents import load_knowledge_chunks


def test_load_knowledge_chunks_returns_one_chunk_per_document(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "password.md").write_text(
        "# Инструкция по сбросу пароля\n"
        "**Версия:** 1\n\n"
        "## 1. Назначение\n"
        "Описание.\n\n"
        "## 2. Шаги\n"
        "1. Откройте портал.\n"
        "2. Смените пароль.\n",
        encoding="utf-8",
    )

    chunks = load_knowledge_chunks(docs_dir)

    assert len(chunks) == 1
    assert {chunk.document for chunk in chunks} == {"Инструкция по сбросу пароля"}
    assert chunks[0].section == "Весь документ"
    assert chunks[0].filename == "password.md"
    assert "## 1. Назначение" in chunks[0].content
    assert "## 2. Шаги" in chunks[0].content
