"""Rubric-based judging and single-retry refinement of generated emails.

Internal service only — no router, no DB access. ``evaluate_with_retry`` owns
the silent single-retry gate loop from ``product_discovery_summary.md``;
``refine`` remains a standalone reusable primitive for the deferred v1.1+
multi-turn refinement path. Calls ``LLMClient.complete`` only; never the
Anthropic SDK directly (ARCHITECTURE.md §3).
"""

from __future__ import annotations

from app.llm.client import LLMClient
from app.llm.prompts import eval_prompt, refine_prompt
from app.schemas.generated_email import EmailDraft, EvalResult, MatchData


async def evaluate_email(
    email: EmailDraft,
    match_data: MatchData,
    contact_name: str | None,
    contact_title: str | None,
    company_name: str,
    role_title: str,
    *,
    llm_client: LLMClient | None = None,
) -> EvalResult:
    """Judge an email against the locked Tier 1 / Tier 2 rubric."""
    client = llm_client or LLMClient()
    return await client.complete(
        eval_prompt(
            email,
            match_data,
            contact_name,
            contact_title,
            company_name,
            role_title,
        ),
        EvalResult,
    )


async def refine(
    email: EmailDraft,
    feedback: str,
    *,
    llm_client: LLMClient | None = None,
) -> EmailDraft:
    """Revise an email to address specific feedback; return a full new draft."""
    client = llm_client or LLMClient()
    return await client.complete(
        refine_prompt(email, feedback),
        EmailDraft,
    )


async def evaluate_with_retry(
    email: EmailDraft,
    match_data: MatchData,
    contact_name: str | None,
    contact_title: str | None,
    company_name: str,
    role_title: str,
    *,
    llm_client: LLMClient | None = None,
) -> tuple[EmailDraft, EvalResult]:
    """Evaluate once; on hard-gate failure, refine once and re-evaluate.

    Returns the second-pass ``(email, eval_result)`` regardless of whether
    gates then pass — no third attempt, no exception on persistent failure.
    Constructs at most one ``LLMClient`` and reuses it across all calls.
    """
    client = llm_client or LLMClient()
    eval_result = await evaluate_email(
        email,
        match_data,
        contact_name,
        contact_title,
        company_name,
        role_title,
        llm_client=client,
    )
    gates = eval_result.gates
    if (
        gates.no_unsupported_claims
        and gates.correct_contact_name_used
        and gates.no_unprompted_gap_admission
    ):
        return email, eval_result

    # violation_detail is required by the judge prompt when a gate fails;
    # fall back only if the model omitted it so refine still receives str.
    feedback = gates.violation_detail or (
        "One or more hard gates failed; revise the email accordingly."
    )
    refined = await refine(email, feedback, llm_client=client)
    second_result = await evaluate_email(
        refined,
        match_data,
        contact_name,
        contact_title,
        company_name,
        role_title,
        llm_client=client,
    )
    return refined, second_result
