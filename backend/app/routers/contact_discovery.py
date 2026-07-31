"""Contact discovery HTTP endpoint (auth required)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.providers.mock import MockProvider
from app.schemas.contact import ContactDiscoveryRequest, ContactDiscoveryResponse
from app.services import contact_discovery as contact_discovery_service

router = APIRouter(tags=["contacts"])


@router.post("/discover", response_model=ContactDiscoveryResponse)
async def discover_contact(
    body: ContactDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactDiscoveryResponse:
    # Config-driven provider list is a Phase 2 concern — MockProvider only for now.
    _ = current_user
    providers = [MockProvider()]
    return await contact_discovery_service.discover_contact(
        db,
        providers,
        body.company_domain,
        body.role_title,
    )
