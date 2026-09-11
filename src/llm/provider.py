import asyncio
import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel

from src.core.config import Settings

StructuredT = TypeVar("StructuredT", bound=BaseModel)
ResponseT = TypeVar("ResponseT")


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool = False


class LLMProvider(Protocol):
    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse: ...

    async def generate_structured(
        self, prompt: str, schema: type[StructuredT], *, system: str | None = None
    ) -> tuple[StructuredT, LLMResponse]: ...


class _BaseProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, LLMResponse] = {}

    async def generate(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        key = self._cache_key(prompt, system)
        if key in self._cache:
            return self._cache[key].__class__(**{**self._cache[key].__dict__, "cached": True})
        response = await self._request(prompt, system=system)
        self._cache[key] = response
        return response

    async def generate_structured(
        self, prompt: str, schema: type[StructuredT], *, system: str | None = None
    ) -> tuple[StructuredT, LLMResponse]:
        instruction = (
            f"{prompt}\nReturn only valid JSON matching this schema: "
            f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        response = await self.generate(instruction, system=system)
        try:
            value = schema.model_validate_json(response.text)
        except Exception:
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match is None:
                raise ValueError("LLM response does not contain valid structured JSON") from None
            value = schema.model_validate_json(match.group(0))
        return value, response

    def _cache_key(self, prompt: str, system: str | None) -> str:
        raw = json.dumps([self.settings.llm_model, system, prompt], ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _request(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        raise NotImplementedError

    async def _with_retries(self, operation: Callable[[], Awaitable[ResponseT]]) -> ResponseT:
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                return await operation()
            except (httpx.HTTPError, TimeoutError):
                if attempt >= self.settings.llm_max_retries:
                    raise
                await asyncio.sleep(0.25 * 2**attempt)
        raise AssertionError("unreachable")


class OllamaProvider(_BaseProvider):
    async def _request(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        async def call() -> LLMResponse:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/api/generate",
                    json={
                        "model": self.settings.llm_model,
                        "prompt": prompt,
                        "system": system or "",
                        "stream": False,
                        "options": {"num_predict": self.settings.llm_max_output_tokens},
                    },
                )
                response.raise_for_status()
                payload = response.json()
                text = payload["response"]
                return LLMResponse(
                    text,
                    payload.get("model", self.settings.llm_model),
                    _tokens(prompt),
                    _tokens(text),
                )

        return await self._with_retries(call)


class OpenAICompatibleProvider(_BaseProvider):
    async def _request(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        async def call() -> LLMResponse:
            headers = (
                {"Authorization": f"Bearer {self.settings.llm_api_key.get_secret_value()}"}
                if self.settings.llm_api_key
                else {}
            )
            messages = ([{"role": "system", "content": system}] if system else []) + [
                {"role": "user", "content": prompt}
            ]
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": self.settings.llm_model,
                        "messages": messages,
                        "stream": False,
                        "max_tokens": self.settings.llm_max_output_tokens,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                text = payload["choices"][0]["message"]["content"]
                usage = payload.get("usage", {})
                return LLMResponse(
                    text,
                    payload.get("model", self.settings.llm_model),
                    usage.get("prompt_tokens", _tokens(prompt)),
                    usage.get("completion_tokens", _tokens(text)),
                )

        return await self._with_retries(call)


def _tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))


def create_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider.lower() == "ollama":
        return OllamaProvider(settings)
    if settings.llm_provider.lower() in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider(settings)
    raise ValueError(f"unsupported LLM provider: {settings.llm_provider}")
