import httpx
import pytest
from pydantic import BaseModel

from src.core.config import Settings
from src.llm.provider import OllamaProvider, OpenAICompatibleProvider, create_provider


class Answer(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_ollama_generate_and_cache(monkeypatch) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"model": "test", "response": "hello"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    provider = OllamaProvider(Settings(llm_model="test"))
    first = await provider.generate("say hi")
    second = await provider.generate("say hi")
    assert first.text == "hello" and second.cached and calls == 1


@pytest.mark.asyncio
async def test_structured_output() -> None:
    provider = OllamaProvider(Settings())
    provider._request = lambda prompt, system=None: _response('{"value":"ok"}')
    value, response = await provider.generate_structured("answer", Answer)
    assert value.value == "ok" and response.output_tokens == 1


async def _response(text: str):
    from src.llm.provider import LLMResponse

    return LLMResponse(text, "test", 1, 1)


def test_provider_switch() -> None:
    assert isinstance(create_provider(Settings(llm_provider="ollama")), OllamaProvider)
    assert isinstance(create_provider(Settings(llm_provider="openai")), OpenAICompatibleProvider)
