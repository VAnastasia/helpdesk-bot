from __future__ import annotations

import httpx

from backend.app.config import Settings


class OpenRouterError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url.rstrip("/"),
            timeout=httpx.Timeout(settings.llm_timeout_seconds),
            headers=self._headers(),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self.settings.openrouter_embedding_model,
            "input": texts,
        }
        data = await self._post("/embeddings", payload)
        embeddings = data.get("data", [])
        if len(embeddings) != len(texts):
            raise OpenRouterError("Embedding response size does not match input size")
        return [item["embedding"] for item in embeddings]

    async def chat(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.openrouter_chat_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 500,
        }
        data = await self._post("/chat/completions", payload)
        choices = data.get("choices") or []
        if not choices:
            raise OpenRouterError("Chat response has no choices")
        content = choices[0].get("message", {}).get("content")
        if not content:
            raise OpenRouterError("Chat response has empty content")
        return content.strip()

    async def _post(self, path: str, payload: dict) -> dict:
        if not self.settings.has_openrouter_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured")
        response = await self._client.post(path, json=payload)
        if response.status_code >= 400:
            raise OpenRouterError(
                f"OpenRouter request failed: {response.status_code} {response.text[:300]}"
            )
        return response.json()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if self.settings.openrouter_http_referer:
            headers["HTTP-Referer"] = self.settings.openrouter_http_referer
        if self.settings.openrouter_x_title:
            headers["X-Title"] = self.settings.openrouter_x_title
        return headers
