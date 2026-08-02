"""Grounded outreach draft from contact context + ``MatchData``.

Internal service only — no router, no DB access. Callers are responsible for
loading contact/company/role context and ensuring ``match_data`` exists before
invoking this. Calls ``LLMClient.complete`` only; never the Anthropic SDK
directly (ARCHITECTURE.md §3).
"""

from __future__ import annotations

from app.llm.client import LLMClient
from app.llm.prompts import email_generation_prompt
from app.schemas.generated_email import EmailDraft, MatchData


async def generate_email(
    contact_name: str | None,
    contact_title: str | None,
    company_name: str,
    role_title: str,
    match_data: MatchData,
    *,
    llm_client: LLMClient | None = None,
) -> EmailDraft:
    """Generate a grounded outreach draft; return the complete ``EmailDraft``."""
    client = llm_client or LLMClient()
    return await client.complete(
        email_generation_prompt(
            contact_name,
            contact_title,
            company_name,
            role_title,
            match_data,
        ),
        EmailDraft,
    )
