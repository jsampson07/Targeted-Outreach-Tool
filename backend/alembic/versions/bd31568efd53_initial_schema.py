"""initial schema

Revision ID: bd31568efd53
Revises:
Create Date: 2026-07-29 15:15:37.958756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bd31568efd53"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Native Postgres enums — created/dropped explicitly per DATA_MODEL.md §3.4.
# Autogenerate inlined these into create_table() without create_type=False and
# omitted drop() in downgrade(); both are corrected here before upgrade.
verification_tier_enum = postgresql.ENUM(
    "verified",
    "pattern_guessed",
    "catch_all",
    "unknown",
    name="verification_tier",
    create_type=False,
)
outcome_event_type_enum = postgresql.ENUM(
    "sent",
    "no_response",
    "replied",
    "interview",
    name="outcome_event_type",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    verification_tier_enum.create(op.get_bind())
    outcome_event_type_enum.create(op.get_bind())

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint("domain", name=op.f("uq_companies_domain")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("best_verification_tier", verification_tier_enum, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column(
            "confidence_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_contacts_company_id_companies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index(
        op.f("ix_contacts_company_id"), "contacts", ["company_id"], unique=False
    )
    op.create_table(
        "job_descriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("role_title", sa.String(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "extracted_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_job_descriptions_company_id_companies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_descriptions")),
    )
    op.create_index(
        op.f("ix_job_descriptions_company_id"),
        "job_descriptions",
        ["company_id"],
        unique=False,
    )
    op.create_table(
        "raw_provider_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("provider_name", sa.String(), nullable=False),
        sa.Column("candidate_name", sa.String(), nullable=True),
        sa.Column("candidate_title", sa.String(), nullable=True),
        sa.Column("candidate_email", sa.String(), nullable=True),
        sa.Column("verification_tier", verification_tier_enum, nullable=False),
        sa.Column(
            "raw_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "queried_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_raw_provider_results_company_id_companies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_provider_results")),
    )
    op.create_index(
        op.f("ix_raw_provider_results_company_id"),
        "raw_provider_results",
        ["company_id"],
        unique=False,
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint(
            "token_hash", name=op.f("uq_refresh_tokens_token_hash")
        ),
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "extracted_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_resumes_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resumes")),
    )
    op.create_index(
        op.f("ix_resumes_user_id"), "resumes", ["user_id"], unique=False
    )
    op.create_table(
        "generated_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("job_description_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("eval_score", sa.Float(), nullable=False),
        sa.Column(
            "eval_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "match_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("gate_passed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_generated_emails_contact_id_contacts"),
        ),
        sa.ForeignKeyConstraint(
            ["job_description_id"],
            ["job_descriptions.id"],
            name=op.f(
                "fk_generated_emails_job_description_id_job_descriptions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes.id"],
            name=op.f("fk_generated_emails_resume_id_resumes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_emails")),
    )
    op.create_index(
        op.f("ix_generated_emails_contact_id"),
        "generated_emails",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_emails_job_description_id"),
        "generated_emails",
        ["job_description_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_emails_resume_id"),
        "generated_emails",
        ["resume_id"],
        unique=False,
    )
    op.create_table(
        "outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generated_email_id", sa.Integer(), nullable=False),
        sa.Column("event_type", outcome_event_type_enum, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["generated_email_id"],
            ["generated_emails.id"],
            name=op.f("fk_outcomes_generated_email_id_generated_emails"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outcomes")),
    )
    op.create_index(
        op.f("ix_outcomes_generated_email_id"),
        "outcomes",
        ["generated_email_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_outcomes_generated_email_id"), table_name="outcomes"
    )
    op.drop_table("outcomes")
    op.drop_index(
        op.f("ix_generated_emails_resume_id"), table_name="generated_emails"
    )
    op.drop_index(
        op.f("ix_generated_emails_job_description_id"),
        table_name="generated_emails",
    )
    op.drop_index(
        op.f("ix_generated_emails_contact_id"), table_name="generated_emails"
    )
    op.drop_table("generated_emails")
    op.drop_index(op.f("ix_resumes_user_id"), table_name="resumes")
    op.drop_table("resumes")
    op.drop_index(
        op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens"
    )
    op.drop_table("refresh_tokens")
    op.drop_index(
        op.f("ix_raw_provider_results_company_id"),
        table_name="raw_provider_results",
    )
    op.drop_table("raw_provider_results")
    op.drop_index(
        op.f("ix_job_descriptions_company_id"), table_name="job_descriptions"
    )
    op.drop_table("job_descriptions")
    op.drop_index(op.f("ix_contacts_company_id"), table_name="contacts")
    op.drop_table("contacts")
    op.drop_table("users")
    op.drop_table("companies")

    # Explicit enum drops — autogenerate omitted these (§3.4 / §3.7).
    outcome_event_type_enum.drop(op.get_bind())
    verification_tier_enum.drop(op.get_bind())
