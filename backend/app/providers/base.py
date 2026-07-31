"""ContactProvider ABC and supporting result schemas.

ARCHITECTURE.md §4: expected failures (rate limits, errors, zero matches)
are status values on ProviderSearchResult — never exceptions. Tiering and
caching live in contact_discovery.py, not here.
"""

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, Field

from app.core.enums import VerificationTier


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class ProviderCandidate(BaseModel):
    name: str | None
    title: str | None
    email: str | None
    verification_tier: VerificationTier
    raw_response: dict


class ProviderSearchResult(BaseModel):
    provider_name: str
    status: ProviderStatus
    candidates: list[ProviderCandidate] = Field(default_factory=list)
    error_message: str | None = None


class ContactProvider(ABC):
    name: str

    @abstractmethod
    async def search(
        self, company_domain: str, role_titles: list[str]
    ) -> ProviderSearchResult:
        ...
