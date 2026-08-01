"""HTTP-level tests for POST /companies/search.

Clearbit is mocked at the httpx layer so these exercise the full
router → service path without real network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient


def _signup(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = "secret-password",
):
    return client.post(
        "/auth/signup",
        json={"email": email, "password": password},
    )


def _auth_headers(
    client: TestClient, email: str, password: str = "secret-password"
) -> dict:
    signup = _signup(client, email=email, password=password)
    assert signup.status_code == 201
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


def _mock_client(get_result) -> MagicMock:
    client = MagicMock()
    client.get = AsyncMock(return_value=get_result)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


def _clearbit_response(payload: list) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.text = ""
    response.json.return_value = payload
    return response


def test_search_companies_happy_path(client: TestClient):
    headers = _auth_headers(client, "company-search@example.com")
    mock_http = _mock_client(
        _clearbit_response(
            [
                {"name": "Stripe", "domain": "stripe.com", "logo": None},
                {"name": "Stripe Atlas", "domain": "stripe.com"},
            ]
        )
    )

    with patch(
        "app.services.company_resolution.httpx.AsyncClient",
        return_value=mock_http,
    ):
        response = client.post(
            "/companies/search",
            headers=headers,
            json={"query": "stripe"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["candidates"] == [
        {"name": "Stripe", "domain": "stripe.com"},
        {"name": "Stripe Atlas", "domain": "stripe.com"},
    ]


def test_search_companies_requires_auth(client: TestClient):
    response = client.post(
        "/companies/search",
        json={"query": "stripe"},
    )
    assert response.status_code == 401
