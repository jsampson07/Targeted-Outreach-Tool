"""Unit tests for company_resolution service.

Outbound Clearbit HTTP is mocked — no real network calls.
Uses stdlib asyncio.run (no pytest-asyncio), matching contact_discovery tests.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.company_resolution import search_companies


def _mock_client(get_result=None, get_side_effect=None) -> MagicMock:
    """Build an AsyncClient stand-in usable as an async context manager."""
    client = MagicMock()
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=get_result)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def _response(*, status_code: int = 200, json_data=None, text: str = "") -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.side_effect = ValueError("No JSON body")
    return response


def test_success_returns_candidates():
    payload = [
        {"name": "Stripe", "domain": "stripe.com", "logo": None},
        {"name": "Stripe Partners", "domain": "stripe-partners.com"},
    ]
    client = _mock_client(get_result=_response(json_data=payload))

    with patch(
        "app.services.company_resolution.httpx.AsyncClient",
        return_value=client,
    ):
        result = asyncio.run(search_companies("stripe"))

    assert len(result.candidates) == 2
    assert result.candidates[0].name == "Stripe"
    assert result.candidates[0].domain == "stripe.com"
    assert result.candidates[1].name == "Stripe Partners"
    assert result.candidates[1].domain == "stripe-partners.com"
    client.get.assert_awaited_once()
    _, kwargs = client.get.await_args
    assert kwargs["params"] == {"query": "stripe"}


def test_legitimate_zero_candidates():
    client = _mock_client(get_result=_response(json_data=[]))

    with patch(
        "app.services.company_resolution.httpx.AsyncClient",
        return_value=client,
    ):
        result = asyncio.run(search_companies("zzzz-nonexistent-co"))

    assert result.candidates == []


def test_timeout_returns_empty_without_raising():
    client = _mock_client(
        get_side_effect=httpx.TimeoutException("request timed out")
    )

    with patch(
        "app.services.company_resolution.httpx.AsyncClient",
        return_value=client,
    ):
        result = asyncio.run(search_companies("acme"))

    assert result.candidates == []


def test_non_200_returns_empty_without_raising():
    client = _mock_client(
        get_result=_response(status_code=503, text="service unavailable")
    )

    with patch(
        "app.services.company_resolution.httpx.AsyncClient",
        return_value=client,
    ):
        result = asyncio.run(search_companies("acme"))

    assert result.candidates == []


def test_malformed_json_returns_empty_without_raising():
    client = _mock_client(
        get_result=_response(status_code=200, json_data=None, text="not-json")
    )

    with patch(
        "app.services.company_resolution.httpx.AsyncClient",
        return_value=client,
    ):
        result = asyncio.run(search_companies("acme"))

    assert result.candidates == []
