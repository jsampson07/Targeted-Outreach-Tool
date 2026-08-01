"""Shared Anthropic LLM wrapper (ARCHITECTURE.md §3).

All LLM-touching services call ``LLMClient.complete`` — none import the
Anthropic SDK directly. Shape: prompt in, Pydantic-validated model out,
with one configurable parse/validation retry that feeds the error back.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from anthropic import APIError, AsyncAnthropic
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import LLMExtractionError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Extraction payloads (skills lists, experience bullets) fit comfortably here.
_MAX_TOKENS = 4096

_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


class LLMClient:
    """Thin async wrapper around Anthropic Messages API + Pydantic validation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = self._settings.llm_model
        self._max_retries = self._settings.llm_max_retries
        # Construct even when key is None — complete() raises a clear
        # LLMExtractionError at call time rather than failing app import.
        self._client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

    async def complete(self, prompt: str, response_schema: type[T]) -> T:
        """Call the model, parse JSON, validate against ``response_schema``.

        On parse/validation failure, retries up to ``settings.llm_max_retries``
        times, feeding the prior raw response and error back as context.
        Exhausted retries (or Anthropic API failures) raise ``LLMExtractionError``.
        """
        if not self._settings.anthropic_api_key:
            raise LLMExtractionError(
                detail="ANTHROPIC_API_KEY is not configured",
                user_message=(
                    "AI extraction is not configured. Please try again later."
                ),
            )

        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        last_error: Exception | None = None
        # Initial attempt + llm_max_retries retries (default 1 → 2 attempts).
        for attempt in range(self._max_retries + 1):
            try:
                raw_text = await self._call_model(messages)
            except APIError as exc:
                raise LLMExtractionError(
                    detail=f"Anthropic API error: {exc!r}",
                ) from exc
            except Exception as exc:
                raise LLMExtractionError(
                    detail=f"Unexpected LLM client failure: {exc!r}",
                ) from exc

            try:
                return self._parse_and_validate(raw_text, response_schema)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                logger.info(
                    "LLM parse/validation failed (attempt %s/%s): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                )
                if attempt >= self._max_retries:
                    break
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": raw_text},
                    {
                        "role": "user",
                        "content": (
                            "Your previous response failed validation with "
                            f"this error:\n{exc}\n\n"
                            "Return a corrected JSON object only — no markdown "
                            "fences, no commentary — that matches the schema "
                            "from the original instructions."
                        ),
                    },
                ]

        raise LLMExtractionError(
            detail=(
                f"LLM extraction failed after {self._max_retries + 1} "
                f"attempt(s): {last_error!r}"
            ),
        )

    async def _call_model(self, messages: list[dict[str, str]]) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            messages=messages,
        )
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        if not parts:
            raise ValueError("Model response contained no text content")
        return "".join(parts)

    @staticmethod
    def _parse_and_validate(raw_text: str, response_schema: type[T]) -> T:
        cleaned = raw_text.strip()
        fence_match = _FENCE_RE.match(cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        data = json.loads(cleaned)
        return response_schema.model_validate(data)
