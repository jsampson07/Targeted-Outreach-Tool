"""Prompt templates for structured LLM calls.

Schemas live in ``app/schemas/`` — this module only formats prompts that
instruct the model to emit JSON matching those existing shapes.
"""

from __future__ import annotations

import json

from app.schemas.generated_email import EmailDraft, EvalResult, MatchData
from app.schemas.job_description import JDExtraction
from app.schemas.resume import ResumeExtraction


def resume_extraction_prompt(raw_text: str) -> str:
    """Build the user prompt for resume → ``ResumeExtraction``."""
    schema_json = json.dumps(
        ResumeExtraction.model_json_schema(), indent=2
    )
    return (
        "Extract structured data from the resume text below.\n"
        "Return ONLY a single JSON object that validates against this "
        "JSON Schema — no markdown fences, no commentary, no extra keys.\n\n"
        f"JSON Schema:\n{schema_json}\n\n"
        "Rules:\n"
        "- skills: short skill/technology strings found in the resume\n"
        "- experience: one entry per role; use null for end_date if current\n"
        "- education: short strings (degree, school, year if present)\n"
        "- If a field is genuinely absent, use an empty list (or null for "
        "end_date), never invent employers or degrees\n\n"
        "Resume text:\n"
        "---\n"
        f"{raw_text}\n"
        "---\n"
    )


def jd_extraction_prompt(raw_text: str) -> str:
    """Build the user prompt for job description → ``JDExtraction``."""
    schema_json = json.dumps(JDExtraction.model_json_schema(), indent=2)
    return (
        "Extract structured data from the job description text below.\n"
        "Return ONLY a single JSON object that validates against this "
        "JSON Schema — no markdown fences, no commentary, no extra keys.\n\n"
        f"JSON Schema:\n{schema_json}\n\n"
        "Rules:\n"
        "- required_skills: skills/technologies the posting requires\n"
        "- responsibilities: concrete duties or outcomes listed\n"
        "- seniority_level: a short label if stated (e.g. \"mid\", "
        "\"senior\"), otherwise null\n"
        "- Do not invent requirements that are not in the text\n\n"
        "Job description text:\n"
        "---\n"
        f"{raw_text}\n"
        "---\n"
    )


def matching_prompt(
    resume_extraction: ResumeExtraction,
    jd_extraction: JDExtraction,
) -> str:
    """Build the user prompt for resume×JD → complete ``MatchData``.

    Completeness matters: ``MatchData`` is later used as eval's ground-truth
    reference for unsupported-claim detection (DATA_MODEL.md §2.7), not merely
    a shortlist of the strongest matches for generation.
    """
    schema_json = json.dumps(MatchData.model_json_schema(), indent=2)
    resume_json = resume_extraction.model_dump_json(indent=2)
    jd_json = jd_extraction.model_dump_json(indent=2)
    return (
        "Compare the structured resume extraction to the structured job "
        "description extraction below and produce a COMPLETE match/gap "
        "analysis.\n"
        "Return ONLY a single JSON object that validates against this "
        "JSON Schema — no markdown fences, no commentary, no extra keys.\n\n"
        f"JSON Schema:\n{schema_json}\n\n"
        "Rules:\n"
        "- skill_matches: one entry for EVERY item in the JD's "
        "required_skills — not just the strongest matches. Set matched=true "
        "only when the resume clearly supports that requirement; put brief "
        "supporting text in resume_evidence, otherwise null.\n"
        "- experience_alignment: one entry for EVERY item in the JD's "
        "responsibilities. strength must be one of \"strong\", \"partial\", "
        "or \"none\"; resume_evidence is null when strength is \"none\".\n"
        "- unmatched_jd_requirements: JD required_skills (and any other JD "
        "requirements) with no credible resume support — the disallow-list "
        "for later email generation.\n"
        "- notable_resume_strengths: resume strengths worth considering even "
        "if not listed as JD requirements.\n"
        "- overall_match_summary: a short framing of the overall fit "
        "(a few sentences).\n"
        "- Do not invent resume evidence that is not present in the resume "
        "extraction. Completeness of the comparison matters more than "
        "optimism about the match.\n\n"
        "Resume extraction (JSON):\n"
        "---\n"
        f"{resume_json}\n"
        "---\n\n"
        "Job description extraction (JSON):\n"
        "---\n"
        f"{jd_json}\n"
        "---\n"
    )


def email_generation_prompt(
    contact_name: str | None,
    contact_title: str | None,
    company_name: str,
    role_title: str,
    match_data: MatchData,
) -> str:
    """Build the user prompt for grounded outreach → ``EmailDraft``."""
    schema_json = json.dumps(EmailDraft.model_json_schema(), indent=2)
    match_json = match_data.model_dump_json(indent=2)
    contact_name_repr = (
        json.dumps(contact_name) if contact_name is not None else "null"
    )
    contact_title_repr = (
        json.dumps(contact_title) if contact_title is not None else "null"
    )
    return (
        "Write a short, professional outreach email grounded in the match/"
        "gap analysis below.\n"
        "Return ONLY a single JSON object that validates against this "
        "JSON Schema — no markdown fences, no commentary, no extra keys.\n\n"
        f"JSON Schema:\n{schema_json}\n\n"
        "Rules:\n"
        "- Select at most 2-3 of the strongest points from match_data — "
        "use your own judgment; do not enumerate every match. An email that "
        "recites every matched skill reads as a resume dump, not outreach.\n"
        "- Never claim anything listed in match_data.unmatched_jd_requirements.\n"
        "- Use overall_match_summary as the framing/angle for the email, not "
        "as a field to quote verbatim.\n"
        "- Address the contact by contact_name / contact_title when provided. "
        "If contact_name is null, use a generic professional greeting "
        '(e.g. "Hi there," or addressing the team) — never fabricate a name.\n'
        "- Reference company_name and role_title naturally for specificity.\n"
        "- Keep tone professional and concise, with a clear call-to-action.\n\n"
        f"Contact name: {contact_name_repr}\n"
        f"Contact title: {contact_title_repr}\n"
        f"Company name: {json.dumps(company_name)}\n"
        f"Role title: {json.dumps(role_title)}\n\n"
        "Match data (JSON):\n"
        "---\n"
        f"{match_json}\n"
        "---\n"
    )


def eval_prompt(
    email: EmailDraft,
    match_data: MatchData,
    contact_name: str | None,
    contact_title: str | None,
    company_name: str,
    role_title: str,
) -> str:
    """Build the user prompt for LLM-as-judge → ``EvalResult``."""
    schema_json = json.dumps(EvalResult.model_json_schema(), indent=2)
    email_json = email.model_dump_json(indent=2)
    match_json = match_data.model_dump_json(indent=2)
    contact_name_repr = (
        json.dumps(contact_name) if contact_name is not None else "null"
    )
    contact_title_repr = (
        json.dumps(contact_title) if contact_title is not None else "null"
    )
    return (
        "You are an independent judge evaluating a cold outreach email "
        "against a locked quality rubric.\n"
        "Return ONLY a single JSON object that validates against this "
        "JSON Schema — no markdown fences, no commentary, no extra keys.\n\n"
        f"JSON Schema:\n{schema_json}\n\n"
        "Tier 1 — Hard gates (binary):\n"
        "- no_unsupported_claims: every factual *candidate-fit* claim in "
        "the email must trace to something in match_data. Claims about "
        "items in unmatched_jd_requirements fail this gate. "
        "company_name and role_title are NOT part of this gate — "
        "referencing the company name or role title is not itself a "
        "claim requiring match_data support; do not false-flag "
        "legitimate company/role references.\n"
        "- correct_contact_name_used: the email must address the contact "
        "correctly using contact_name / contact_title when provided. If "
        "contact_name is null, a generic professional greeting (e.g. "
        '"Hi there," or addressing the team) PASSES — fabricating a name '
        "fails.\n"
        "If either gate is false, populate violation_detail with free-form "
        "text naming the specific problem (which claim is unsupported, or "
        "how the contact name/title was wrong). If both gates pass, set "
        "violation_detail to null.\n\n"
        "Tier 2 — Graded dimensions (integers 1–5 each):\n"
        "- role_company_specificity: company_name and role_title below "
        "are trusted ground truth (passed through from already-verified "
        "DB rows, not LLM-generated). Grade whether the email correctly "
        "and specifically references *this* company and role — not "
        "merely whether it sounds specific in the abstract.\n"
        "- relevance_alignment (to the match data / role)\n"
        "- tone_professionalism\n"
        "- conciseness\n"
        "- clear_cta\n\n"
        f"Contact name: {contact_name_repr}\n"
        f"Contact title: {contact_title_repr}\n"
        f"Company name: {json.dumps(company_name)}\n"
        f"Role title: {json.dumps(role_title)}\n\n"
        "Email draft (JSON):\n"
        "---\n"
        f"{email_json}\n"
        "---\n\n"
        "Match data ground-truth reference (JSON):\n"
        "---\n"
        f"{match_json}\n"
        "---\n"
    )


def refine_prompt(email: EmailDraft, feedback: str) -> str:
    """Build the user prompt for feedback-driven revision → ``EmailDraft``."""
    schema_json = json.dumps(EmailDraft.model_json_schema(), indent=2)
    email_json = email.model_dump_json(indent=2)
    return (
        "Revise the outreach email below to address the specific feedback. "
        "Preserve what already works; return a complete new draft (not a "
        "diff).\n"
        "Return ONLY a single JSON object that validates against this "
        "JSON Schema — no markdown fences, no commentary, no extra keys.\n\n"
        f"JSON Schema:\n{schema_json}\n\n"
        "Feedback to address:\n"
        "---\n"
        f"{feedback}\n"
        "---\n\n"
        "Original email draft (JSON):\n"
        "---\n"
        f"{email_json}\n"
        "---\n"
    )
