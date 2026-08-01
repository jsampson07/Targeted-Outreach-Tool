"""Company name-resolution HTTP endpoint (auth required)."""

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.company import CompanySearchRequest, CompanySearchResponse
from app.services import company_resolution as company_resolution_service

router = APIRouter(tags=["companies"])


@router.post("/search", response_model=CompanySearchResponse)
async def search_companies(
    body: CompanySearchRequest,
    current_user: User = Depends(get_current_user),
) -> CompanySearchResponse:
    _ = current_user
    return await company_resolution_service.search_companies(body.query)
