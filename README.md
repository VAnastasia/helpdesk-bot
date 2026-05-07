# HelpBot

HelpBot — standalone MVP веб-чата для внутренней IT-поддержки. Backend построен на FastAPI, RAG использует Markdown-базу знаний из `backend/docs`, PostgreSQL с pgvector и OpenRouter для embeddings и генерации ответов.

## Быстрый старт

1. Создайте `.env` из шаблона:

   ```bash
   cp .env.example .env
   ```

2. Заполните `OPENROUTER_API_KEY` в `.env`.

3. Запустите проект:

   ```bash
   docker compose up --build
   ```

4. Откройте `http://localhost:8000`.

## API

- `GET /` — веб-интерфейс чата.
- `GET /health` — проверка API и PostgreSQL.
- `POST /api/chat` — ответ HelpBot.

Пример запроса:

```json
{ "message": "Как сбросить пароль?" }
```

Пример ответа:

```json
{
  "answer": "...",
  "sources": [{ "document": "...", "section": "..." }],
  "fallback": false
}
```

## Настройки моделей

Модели задаются через `.env`:

- `OPENROUTER_CHAT_MODEL`
- `OPENROUTER_EMBEDDING_MODEL`
- `RAG_SIMILARITY_THRESHOLD`

Для RAG-only режима ответ без релевантного источника возвращается как fallback.
