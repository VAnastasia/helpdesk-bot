import pytest

from backend.app.config import Settings
from backend.app.openrouter import OpenRouterClient


@pytest.mark.asyncio
async def test_chat_payload_does_not_include_legacy_stop_tokens() -> None:
    client = OpenRouterClient(Settings(openrouter_api_key="test-key"))
    captured_payload: dict = {}

    async def fake_post(path: str, payload: dict) -> dict:
        captured_payload["path"] = path
        captured_payload["payload"] = payload
        return {"choices": [{"message": {"content": "Готово"}}]}

    client._post = fake_post  # type: ignore[method-assign]

    try:
        answer = await client.chat([{"role": "user", "content": "Вопрос"}])
    finally:
        await client.close()

    assert answer == "Готово"
    assert captured_payload["path"] == "/chat/completions"
    assert "stop" not in captured_payload["payload"]
