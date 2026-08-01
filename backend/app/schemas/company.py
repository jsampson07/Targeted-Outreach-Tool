"""Company name-resolution I/O schemas (DATA_MODEL.md §2.4.1).

No CompanyOut here — that schema is a separate, not-yet-needed piece.
These schemas back a lookup endpoint with no backing table.
"""

from pydantic import BaseModel


class CompanySearchRequest(BaseModel):
    query: str  # raw user-typed company name


class CompanySearchCandidate(BaseModel):
    name: str
    domain: str


class CompanySearchResponse(BaseModel):
    candidates: list[CompanySearchCandidate]
