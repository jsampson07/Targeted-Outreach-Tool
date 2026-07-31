"""Scriptable ContactProvider peer for local development and unit tests.

Same ABC and ProviderSearchResult shape as real providers — contact_discovery
cannot tell mock from real (ARCHITECTURE.md §4).
"""

from app.providers.base import (
    ContactProvider,
    ProviderSearchResult,
    ProviderStatus,
)


class MockProvider(ContactProvider):
    name = "mock"

    def __init__(
        self,
        scripted: dict[str, list[ProviderSearchResult]] | None = None,
        default: ProviderSearchResult | None = None,
    ) -> None:
        self._scripted = scripted or {}
        # Per-domain index into the scripted queue — one entry consumed per
        # search() call. A discovery run may call up to 4 times per domain
        # (once per DISCOVERY_TIERS entry).
        self._call_index: dict[str, int] = {}
        self._default = default or ProviderSearchResult(
            provider_name=self.name,
            status=ProviderStatus.SUCCESS,
            candidates=[],
        )

    async def search(
        self, company_domain: str, role_titles: list[str]
    ) -> ProviderSearchResult:
        queue = self._scripted.get(company_domain)
        if queue is None:
            return self._default

        idx = self._call_index.get(company_domain, 0)
        self._call_index[company_domain] = idx + 1
        if idx < len(queue):
            return queue[idx]
        return self._default
