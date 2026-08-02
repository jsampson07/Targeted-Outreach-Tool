"""Match/gap analysis: ``ResumeExtraction`` × ``JDExtraction`` → ``MatchData``.

Internal service only — no router, no DB access. Callers
(``generated_emails.py``) are responsible for ensuring extractions exist
before invoking this. Calls ``LLMClient.complete`` only; never the
Anthropic SDK directly (ARCHITECTURE.md §3).
"""

from __future__ import annotations

from app.llm.client import LLMClient
from app.llm.prompts import matching_prompt
from app.schemas.generated_email import MatchData
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ResumeExtraction


async def generate_match_data(
    resume_extraction: ResumeExtraction,
    jd_extraction: JDExtraction,
    *,
    llm_client: LLMClient | None = None,
) -> MatchData:
    """Compare resume and JD extractions; return the complete ``MatchData``."""
    client = llm_client or LLMClient()
    return await client.complete(
        matching_prompt(resume_extraction, jd_extraction),
        MatchData,
    )
