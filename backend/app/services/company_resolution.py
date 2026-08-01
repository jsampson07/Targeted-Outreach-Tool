"""Company name → domain candidates via Clearbit Autocomplete (ARCHITECTURE.md §7).

Never writes to COMPANIES — that table is only written later inside
contact_discovery.py after the user selects a candidate and submits a
real discovery request (DATA_MODEL.md §2.4.1).
"""

import logging

import httpx

from app.schemas.company import CompanySearchCandidate, CompanySearchResponse

logger = logging.getLogger(__name__)

CLEARBIT_AUTOCOMPLETE_URL = (
    "https://autocomplete.clearbit.com/v1/companies/suggest"
)
# Chosen at implementation time — no prior doc specified a timeout value.
REQUEST_TIMEOUT_SECONDS = 5.0


async def search_companies(query: str) -> CompanySearchResponse:
    """Resolve a typed company name into name+domain candidates.

    Never raises for zero matches, timeout, non-200, or malformed JSON —
    all of those return ``CompanySearchResponse(candidates=[])``. Failure
    detail is logged internally so zero-matches and real Clearbit failures
    stay distinguishable in logs (ARCHITECTURE.md §6 / §7).
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(
                CLEARBIT_AUTOCOMPLETE_URL,
                params={"query": query},
            )
    except httpx.TimeoutException:
        logger.warning(
            "Clearbit autocomplete timed out after %ss for query=%r",
            REQUEST_TIMEOUT_SECONDS,
            query,
        )
        return CompanySearchResponse(candidates=[])
    except httpx.HTTPError as exc:
        logger.warning(
            "Clearbit autocomplete network error for query=%r: %s",
            query,
            exc,
        )
        return CompanySearchResponse(candidates=[])

    if response.status_code != 200:
        logger.warning(
            "Clearbit autocomplete non-200 status=%s for query=%r body=%r",
            response.status_code,
            query,
            response.text[:200],
        )
        return CompanySearchResponse(candidates=[])

    try:
        payload = response.json()
    except ValueError:
        logger.warning(
            "Clearbit autocomplete malformed JSON for query=%r",
            query,
        )
        return CompanySearchResponse(candidates=[])

    if not isinstance(payload, list):
        logger.warning(
            "Clearbit autocomplete unexpected JSON shape for query=%r: %s",
            query,
            type(payload).__name__,
        )
        return CompanySearchResponse(candidates=[])

    candidates: list[CompanySearchCandidate] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        domain = item.get("domain")
        if isinstance(name, str) and name and isinstance(domain, str) and domain:
            candidates.append(CompanySearchCandidate(name=name, domain=domain))

    if not candidates:
        logger.info(
            "Clearbit autocomplete returned zero usable candidates for query=%r",
            query,
        )

    return CompanySearchResponse(candidates=candidates)
