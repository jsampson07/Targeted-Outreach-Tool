"""Shared Postgres-persisted enums.

ARCHITECTURE.md §4.4: VerificationTier lives in a neutral shared location
so SQLAlchemy models and Pydantic schemas import the same definition
without drift. OutcomeEventType follows the same rule (DATA_MODEL.md
§2.8 / §3.4).
"""

from enum import Enum

from sqlalchemy import Enum as SAEnum


class VerificationTier(str, Enum):
    VERIFIED = "verified"
    PATTERN_GUESSED = "pattern_guessed"
    CATCH_ALL = "catch_all"
    UNKNOWN = "unknown"


class OutcomeEventType(str, Enum):
    SENT = "sent"
    NO_RESPONSE = "no_response"
    REPLIED = "replied"
    INTERVIEW = "interview"


# One SQLAlchemy Enum type per Postgres native enum — reused by every
# column that persists that enum so create/drop happens once (§3.4).
verification_tier_enum = SAEnum(
    VerificationTier,
    name="verification_tier",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    create_type=True,
)

outcome_event_type_enum = SAEnum(
    OutcomeEventType,
    name="outcome_event_type",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    create_type=True,
)
