from pathlib import Path

from backend.app.documents import load_knowledge_chunks


def test_load_knowledge_chunks_splits_document_by_h2_sections(tmp_path: Path) -> None:
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

    assert len(chunks) == 2
    assert {chunk.document for chunk in chunks} == {"Инструкция по сбросу пароля"}
    assert [chunk.section for chunk in chunks] == ["1. Назначение", "2. Шаги"]
    assert {chunk.filename for chunk in chunks} == {"password.md"}
    assert "## 1. Назначение" in chunks[0].content
    assert "## 2. Шаги" not in chunks[0].content
    assert "## 2. Шаги" in chunks[1].content
    assert "1. Откройте портал." in chunks[1].content
    assert len({chunk.id for chunk in chunks}) == 2


def test_load_knowledge_chunks_keeps_h3_inside_parent_h2(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "vpn.md").write_text(
        "# VPN\n\n"
        "## 1. Типовые проблемы\n"
        "Описание.\n\n"
        "### Сервер недоступен\n"
        "Проверьте интернет.\n\n"
        "## 2. Безопасность\n"
        "Используйте VPN только для рабочих задач.\n",
        encoding="utf-8",
    )

    chunks = load_knowledge_chunks(docs_dir)

    assert len(chunks) == 2
    assert chunks[0].section == "1. Типовые проблемы"
    assert "### Сервер недоступен" in chunks[0].content
    assert "## 2. Безопасность" not in chunks[0].content


def test_load_knowledge_chunks_falls_back_to_whole_document_without_h2(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "contacts.md").write_text(
        "# Контакты IT\n"
        "Пишите на incident@company.ru.\n",
        encoding="utf-8",
    )

    chunks = load_knowledge_chunks(docs_dir)

    assert len(chunks) == 1
    assert chunks[0].document == "Контакты IT"
    assert chunks[0].section == "Весь документ"
    assert "incident@company.ru" in chunks[0].content
