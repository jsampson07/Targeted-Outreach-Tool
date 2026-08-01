"""Contact discovery HTTP endpoint (auth required)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.providers.base import ContactProvider
from app.providers.hunter import HunterProvider
from app.providers.mock import MockProvider
from app.schemas.contact import ContactDiscoveryRequest, ContactDiscoveryResponse
from app.services import contact_discovery as contact_discovery_service

router = APIRouter(tags=["contacts"])


def _build_providers() -> list[ContactProvider]:
    settings = get_settings()
    if settings.contact_provider == "hunter":
        return [HunterProvider(api_key=settings.hunter_api_key)]
    return [MockProvider()]


@router.post("/discover", response_model=ContactDiscoveryResponse)
async def discover_contact(
    body: ContactDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactDiscoveryResponse:
    _ = current_user
    return await contact_discovery_service.discover_contact(
        db,
        _build_providers(),
        body.company_domain,
        body.role_title,
    )
