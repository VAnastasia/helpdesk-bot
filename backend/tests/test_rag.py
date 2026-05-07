from backend.app.contracts import Source
from backend.app.config import _known_embedding_dimensions
from backend.app.db import _can_create_hnsw_index, _parse_vector_dimensions
from backend.app.rag import (
    _answer_has_source,
    _fallback,
    _is_out_of_scope,
    _openrouter_role,
    _strip_trailing_source,
    _vector_literal,
)


def test_fallback_has_no_sources() -> None:
    response = _fallback()

    assert response.fallback is True
    assert response.sources == []
    assert "нет точной информации" in response.answer


def test_out_of_scope_detects_hr_questions() -> None:
    assert _is_out_of_scope("Сколько дней отпуска мне положено?")


def test_answer_source_validation() -> None:
    sources = [Source(document="Инструкция по VPN", section="Настройка")]

    assert _answer_has_source(
        "Сделайте так.\n\nИсточник: [Документ: Инструкция по VPN, раздел: Настройка]",
        sources,
    )
    assert not _answer_has_source("Сделайте так.", sources)


def test_vector_literal_format() -> None:
    assert _vector_literal([0.1, -0.25]) == "[0.10000000,-0.25000000]"


def test_openrouter_role_mapping() -> None:
    assert _openrouter_role("human") == "user"
    assert _openrouter_role("ai") == "assistant"
    assert _openrouter_role("system") == "system"


def test_strip_trailing_source_with_prefix() -> None:
    answer = (
        "Сделайте так:\n"
        "1. Откройте портал.\n\n"
        "Источник: [Документ: FAQ по лицензиям, раздел: 1. Figma]"
    )

    assert _strip_trailing_source(answer) == "Сделайте так:\n1. Откройте портал."


def test_strip_trailing_source_without_prefix() -> None:
    answer = "Ответ.\n\n[Документ: FAQ по лицензиям, раздел: 1. Figma]"

    assert _strip_trailing_source(answer) == "Ответ."


def test_strip_trailing_source_at_end_of_sentence() -> None:
    answer = "Создайте заявку в Service Desk [Документ: FAQ, раздел: 1. Figma]"

    assert _strip_trailing_source(answer) == "Создайте заявку в Service Desk"


def test_strip_trailing_source_at_end_of_sentence_with_period() -> None:
    answer = "Создайте заявку в Service Desk [Документ: FAQ, раздел: 1. Figma]."

    assert _strip_trailing_source(answer) == "Создайте заявку в Service Desk"


def test_strip_trailing_source_keeps_regular_answer() -> None:
    answer = "Ответ без отдельного source-блока."

    assert _strip_trailing_source(answer) == answer


def test_parse_vector_dimensions() -> None:
    assert _parse_vector_dimensions("vector(3072)") == 3072
    assert _parse_vector_dimensions("vector(1536)") == 1536
    assert _parse_vector_dimensions("text") is None


def test_known_embedding_dimensions() -> None:
    assert _known_embedding_dimensions("openai/text-embedding-3-large") == 3072
    assert _known_embedding_dimensions("openai/text-embedding-3-small") == 1536
    assert _known_embedding_dimensions("some/custom-model") is None


def test_hnsw_dimension_limit() -> None:
    assert _can_create_hnsw_index(1536)
    assert _can_create_hnsw_index(2000)
    assert not _can_create_hnsw_index(2001)
    assert not _can_create_hnsw_index(3072)
