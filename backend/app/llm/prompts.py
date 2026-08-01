"""Prompt templates for structured LLM extraction.

Schemas live in ``app/schemas/`` — this module only formats prompts that
instruct the model to emit JSON matching those existing shapes.
"""

from __future__ import annotations

import json

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
