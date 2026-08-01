"""Unit tests for LLMClient — Anthropic SDK fully mocked (no live API calls)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.exceptions import LLMExtractionError
from app.llm.client import LLMClient


class _SampleSchema(BaseModel):
    name: str
    count: int


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+psycopg2://x:x@localhost/x",
        "jwt_secret_key": "test-secret",
        "anthropic_api_key": "test-key",
        "llm_model": "claude-haiku-4-5",
        "llm_max_retries": 1,
    }
    base.update(overrides)
    return Settings(**base)


def _message_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    block.type = "text"
    msg = MagicMock()
    msg.content = [block]
    return msg


def _client_with_mock_create(side_effect=None, return_value=None) -> tuple[LLMClient, MagicMock]:
    mock_async = MagicMock()
    create = AsyncMock()
    if side_effect is not None:
        create.side_effect = side_effect
    else:
        create.return_value = return_value
    mock_async.messages.create = create

    with patch("app.llm.client.AsyncAnthropic", return_value=mock_async):
        client = LLMClient(settings=_settings())
    # Patch applied only during __init__; re-bind the instance client.
    client._client = mock_async
    return client, create


def test_complete_success_first_attempt():
    payload = {"name": "Ada", "count": 3}
    client, create = _client_with_mock_create(
        return_value=_message_response(json.dumps(payload))
    )

    result = asyncio.run(
        client.complete("extract this", _SampleSchema)
    )

    assert result == _SampleSchema(name="Ada", count=3)
    assert create.await_count == 1


def test_complete_retries_once_then_succeeds():
    bad = _message_response("not-json")
    good = _message_response(json.dumps({"name": "Grace", "count": 1}))
    client, create = _client_with_mock_create(side_effect=[bad, good])

    result = asyncio.run(
        client.complete("extract this", _SampleSchema)
    )

    assert result == _SampleSchema(name="Grace", count=1)
    assert create.await_count == 2
    # Second call includes the assistant's bad response + correction turn.
    second_messages = create.await_args_list[1].kwargs["messages"]
    assert len(second_messages) == 3
    assert second_messages[1]["role"] == "assistant"
    assert second_messages[1]["content"] == "not-json"
    assert second_messages[2]["role"] == "user"
    assert "failed validation" in second_messages[2]["content"]


def test_complete_retry_exhausted_raises_llm_extraction_error():
    bad = _message_response('{"name": 123, "count": "nope"}')
    client, create = _client_with_mock_create(side_effect=[bad, bad])

    with pytest.raises(LLMExtractionError) as exc_info:
        asyncio.run(client.complete("extract this", _SampleSchema))

    assert exc_info.value.status_code == 502
    assert create.await_count == 2


def test_complete_accepts_markdown_fenced_json():
    fenced = "```json\n" + json.dumps({"name": "Lin", "count": 2}) + "\n```"
    client, create = _client_with_mock_create(
        return_value=_message_response(fenced)
    )

    result = asyncio.run(
        client.complete("extract this", _SampleSchema)
    )

    assert result.name == "Lin"
    assert create.await_count == 1


def test_complete_missing_api_key_raises():
    with patch("app.llm.client.AsyncAnthropic") as mock_cls:
        mock_cls.return_value = MagicMock()
        client = LLMClient(settings=_settings(anthropic_api_key=None))

    with pytest.raises(LLMExtractionError) as exc_info:
        asyncio.run(client.complete("extract this", _SampleSchema))

    assert "not configured" in exc_info.value.detail
