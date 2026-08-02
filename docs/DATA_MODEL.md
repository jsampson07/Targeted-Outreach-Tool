# Data Model Reference

*Companion to `product_discovery_summary.md`, which locks the 9 core entities and their relationships, and to `ARCHITECTURE.md`. This document covers how those entities are expressed as Pydantic schemas and how the first Alembic migration is structured.*

---

## 1. General Pydantic Schema Pattern

**Decision:** Most entities get up to three schema classes rather than one:

- **`XBase`** — fields common to both create and read variants, so they're defined once.
- **`XCreate`** — required input when the entity is first created. Never includes `id` or server-generated fields like `created_at`.
- **`XOut`** — safe/useful fields to return. Includes `id`, timestamps, and everything the frontend needs — nothing it shouldn't see. Uses `model_config = ConfigDict(from_attributes=True)` to read directly off ORM objects.

**Reasoning:** This is the practical mechanism behind the models/schemas boundary described in `ARCHITECTURE.md` §2 — different moments in an entity's life legitimately expose different fields, and `response_model=XOut` acts as an explicit allowlist so FastAPI can never accidentally serialize a DB-only column (e.g. a password hash) that happens to be reachable on the ORM object.

**Not every entity needs all three variants.** Several entities in this project are never directly created by a user-facing API call — they're populated as a *side effect* of another operation (a search, a generation run). Those get an `Out` schema and, where relevant, a different request schema entirely (see `COMPANIES`, `RAW_PROVIDER_RESULTS`, `GENERATED_EMAILS` below) — forcing every entity into a `Create` schema would misrepresent how it actually gets written.

---

## 2. Entity-by-Entity Schemas

### 2.1 USERS

```python
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Decision detail:** `UserCreate.password` (plaintext, in transit only) is deliberately named differently from the ORM's `password_hash` column. This is a small guard against a copy-paste bug that assigns the raw password straight into the hash column because the field names happened to match.

### 2.2 RESUMES

```python
class ResumeCreate(BaseModel):
    raw_text: str

class ResumeOut(BaseModel):
    id: int
    user_id: int
    raw_text: str
    extracted_data: "ResumeExtraction | None"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExperienceEntry(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str | None
    bullet_points: list[str]

class ResumeExtraction(BaseModel):
    skills: list[str]
    experience: list[ExperienceEntry]
    education: list[str]
```

**Assumption:** File parsing (PDF/docx → text) happens in the router/service before `ResumeCreate` is constructed, so this schema only ever handles text, never file bytes — keeping Pydantic's job "validate structured data" rather than "handle file I/O."

### 2.3 JOB_DESCRIPTIONS

Structurally identical to Resumes:

```python
class JobDescriptionCreate(BaseModel):
    raw_text: str
    company_id: int
    role_title: str

class JobDescriptionOut(BaseModel):
    id: int
    company_id: int
    role_title: str
    raw_text: str
    extracted_data: "JDExtraction | None"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class JDExtraction(BaseModel):
    required_skills: list[str]
    responsibilities: list[str]
    seniority_level: str | None
```

### 2.4 COMPANIES

```python
class CompanyOut(BaseModel):
    id: int
    name: str
    domain: str
    model_config = ConfigDict(from_attributes=True)
```

**Decision:** No `CompanyCreate`. A user never directly creates a `Company` row through an API call — the flow is: user submits a search request, and `contact_discovery.py` internally decides whether to reuse an existing row or insert a new one. The search input is its own schema:

```python
class ContactDiscoveryRequest(BaseModel):
    company_domain: str
    role_title: str
```

**Reasoning:** Not every table needs a `Create` schema mirroring a REST "create this resource" pattern — `COMPANIES` is populated as a side effect of searching, not as its own direct user action.

### 2.4.1 Company Name Resolution (pre-search step, no backing table)

```python
class CompanySearchRequest(BaseModel):
    query: str  # raw user-typed company name

class CompanySearchCandidate(BaseModel):
    name: str
    domain: str

class CompanySearchResponse(BaseModel):
    candidates: list[CompanySearchCandidate]
```

**Decision:** These schemas back a distinct endpoint that runs *before* `ContactDiscoveryRequest`, not a variant of it. A user types a company name; this endpoint returns candidates for the user to pick from (see `ARCHITECTURE.md` §7); whichever `domain` the user ends up confirming — from a candidate or from the manual-entry fallback — is what populates `ContactDiscoveryRequest.company_domain` in the very next request. No table backs `CompanySearchResponse` itself, for the same reason `ContactDiscoveryRequest` has none: this is a lookup, not a resource being created. `COMPANIES` is still the only table actually written to, and only later, inside `contact_discovery.py`, exactly as already designed.

### 2.5 RAW_PROVIDER_RESULTS

```python
class RawProviderResultOut(BaseModel):
    id: int
    company_id: int
    provider_name: str
    candidate_name: str | None
    candidate_title: str | None
    candidate_email: str | None
    verification_tier: VerificationTier
    raw_response: dict
    queried_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Decision:** No user-facing `Create` — rows are populated internally from `ContactProvider.search()` output (see `ARCHITECTURE.md` §4.4). This schema exists mainly for internal/debug/admin use and as the explicit translation point between `ProviderCandidate` and the DB row, not for a public API route.

### 2.6 CONTACTS

```python
class ConfidenceBreakdown(BaseModel):
    verification_tier_score: float
    cross_provider_corroboration: bool
    employment_currency_signal: str   # "current" | "stale" | "unknown"
    domain_check_passed: bool
    name_collision_detected: bool

class ContactOut(BaseModel):
    id: int
    company_id: int
    name: str | None
    title: str | None
    email: str | None
    best_verification_tier: VerificationTier
    confidence_score: float
    confidence_breakdown: ConfidenceBreakdown
    model_config = ConfigDict(from_attributes=True)
```

**Decision:** `confidence_breakdown` is exposed through the API (not just the internal `confidence_score` float), and is **persisted** as a JSONB column on `CONTACTS` (see §3.5) rather than computed at read time.

**Reasoning:** Exposing the full breakdown avoids re-introducing the "hand-waved single score" problem at the API boundary that the product doc explicitly designed the confidence model to avoid. Persisting it is cheap — written once at contact-creation/reconciliation time, read back as a normal column — and is strictly less read-time work than recomputing an aggregation from `RAW_PROVIDER_RESULTS` on every fetch. The one real cost: if reconciliation ever reruns for an existing contact, the persisted breakdown has to be recomputed and overwritten at that point, not left stale.

**Deferred, not decided:** Which subset of `confidence_breakdown` fields the frontend actually surfaces to the user is a UI-copy decision, not a schema decision — the schema intentionally exposes the full object; the frontend picks what to render.

### 2.6.1 ContactDiscoveryResponse (wraps ContactOut for the discovery endpoint only)

```python
class ContactDiscoveryResponse(BaseModel):
    contact: ContactOut | None
    fallback_reason: str | None
    tier_used: str | None
```

**Decision:** Per-search context (which tier hit, why earlier tiers were skipped) is
returned transiently by the discovery endpoint — never persisted, never added to
`ContactOut`. `ContactOut` stays the stable, search-independent resource; this mirrors
the same stable-vs-per-search boundary `product_discovery_summary.md` already draws
when explaining why `SEARCHES` is deferred. `contact` is nullable to represent every
tier being exhausted with zero candidates found.

### 2.7 GENERATED_EMAILS

```python
class EvalGates(BaseModel):
    no_unsupported_claims: bool
    correct_contact_name_used: bool
    violation_detail: str | None = None

class EvalDimensions(BaseModel):
    role_company_specificity: int   # 1-5
    relevance_alignment: int
    tone_professionalism: int
    conciseness: int
    clear_cta: int

class EvalBreakdown(BaseModel):
    gates: EvalGates
    dimensions: EvalDimensions

class EvalResult(EvalBreakdown):
    """Raw shape returned by the LLM-judge call — before it's decided
    whether to trigger refine() and before it's persisted."""
    pass

class EmailDraft(BaseModel):
    subject: str
    body: str

class SkillMatch(BaseModel):
    jd_requirement: str
    matched: bool
    resume_evidence: str | None

class ExperienceAlignment(BaseModel):
    jd_responsibility: str
    resume_evidence: str | None
    strength: Literal["strong", "partial", "none"]

class MatchData(BaseModel):
    skill_matches: list[SkillMatch]
    experience_alignment: list[ExperienceAlignment]
    unmatched_jd_requirements: list[str]
    notable_resume_strengths: list[str]
    overall_match_summary: str

class GenerateEmailRequest(BaseModel):
    contact_id: int
    resume_id: int
    job_description_id: int

class GeneratedEmailOut(BaseModel):
    id: int
    contact_id: int
    resume_id: int
    job_description_id: int
    subject: str
    body: str
    eval_score: float
    eval_breakdown: EvalBreakdown
    match_data: MatchData
    gate_passed: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Decision:** No `GeneratedEmailCreate` — like `COMPANIES`, this entity is the *output* of a flow (IDs in → match/generate/eval → a row out), not something a user POSTs as a ready-made email. The request body for that flow is `GenerateEmailRequest` below — not a create schema.

**Decision (gap filled):** `GenerateEmailRequest` was never defined in this document previously — §2.7 only specified `GeneratedEmailOut` and noted "no `GeneratedEmailCreate`" without naming the actual request body. That was a real documentation gap, not a rename: the endpoint takes `{contact_id, resume_id, job_description_id}` and the server owns generation, scoring, and persistence. Added here to match `app/schemas/generated_email.py` / `POST /generated-emails`.

**Decision (revision):** `EvalGates.violation_detail: str | None = None` was added after the original schema lock. It is free-form text (not a fixed violation-type enum) populated by the LLM judge only when at least one Tier 1 gate is `False`, naming the specific problem (e.g. which claim isn't traceable to `match_data`, or how the contact name/title was wrong). It exists solely to feed `refine(email, feedback)` — it is never shown to the user and is not persisted as its own column (it rides along inside the persisted `eval_breakdown` JSONB on `GENERATED_EMAILS`). A fixed enum was considered and rejected: gate failures are too situation-specific for a closed category list to stay useful as refine feedback without constantly expanding the enum.

**Decision:** `EmailDraft` is the ephemeral LLM structured-output shape for generation and refine (`subject` + `body` only). It is not a persisted entity and has no backing table — `GENERATED_EMAILS` stores subject/body as columns on the row written by `app/services/generated_emails.py`. Keeping draft I/O separate from `GeneratedEmailOut` avoids conflating "what the model just produced" with "what was saved and returned to the client."

**Decision:** Match/gap analysis is persisted as a `match_data` JSONB field on `GENERATED_EMAILS`, rather than left ephemeral (computed at generation time and discarded). This matches the same "persist for audit fidelity" tradeoff already accepted for `RAW_PROVIDER_RESULTS` in the product doc, and enables future analytics (e.g. reply rate vs. skill-match completeness) without needing a schema change later.

**`MatchData`'s role — this is important and was explicitly clarified during design:**
- `MatchData` is the *complete* comparison between resume and JD — every skill checked, every responsibility assessed, every gap named. Completeness here is what makes it useful for grounding and evaluation.
- It is **not** a template or checklist the generated email is expected to work through. The email is not validated against `match_data` field-by-field, and it should not mention most of what's in it — an email that recited every matched skill would read as a resume dump, not outreach.
- In the **generation prompt** (`email_generation.py`), `match_data` is passed in full as *guidance*: the model is instructed to select at most 2-3 of the strongest points and write around them naturally, not enumerate everything. `unmatched_jd_requirements` specifically exists as the disallow-list for generation — nothing in it should be claimed.
- In the **eval/judge prompt** (`eval.py`), `match_data` plays a different role: a ground-truth *reference to verify against*. The Tier 1 hard gate ("no unsupported claims") checks whether every claim actually made in the email traces back to something in `match_data` — it doesn't check for completeness, only for the absence of false claims. This is why the rubric structurally does not reward or require resume-dumping: conciseness and specificity are separate graded dimensions, and the hard gate only ever checks precision, never recall.
- `overall_match_summary` is the one field meant for direct consumption in the generation prompt (the compressed framing/angle); the other fields are the selectable menu and the verification reference.

**Decision:** For v1, the LLM's selection of which 2-3 match points to feature in a given email is **free-form** — the model chooses based on its own judgment each time, rather than the pipeline pre-ranking `skill_matches` and constraining the model to the top-ranked items.

**Alternative considered:** Ranking matches by a relevance heuristic before prompting, and instructing the model to prefer top-ranked items. More debuggable/reproducible (clearer "why did it pick this one"), but more code in the matching step. Deferred — free-form is simpler to build, and inconsistent-but-plausible selection is treated as an acceptable v1 behavior to observe before deciding it's a real problem worth engineering around.

### 2.8 OUTCOMES

```python
class OutcomeEventType(str, Enum):
    SENT = "sent"
    NO_RESPONSE = "no_response"
    REPLIED = "replied"
    INTERVIEW = "interview"

class OutcomeCreate(BaseModel):
    generated_email_id: int
    event_type: OutcomeEventType

class OutcomeOut(BaseModel):
    id: int
    generated_email_id: int
    event_type: OutcomeEventType
    occurred_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Decision:** No `OutcomeUpdate` schema. `OUTCOMES` is an append-only event log per the product doc — the only valid operations are "log a new event" and "read history." A need to edit or delete a row would indicate the model is being used incorrectly (a correction should be a new appended event, not a mutation).

### 2.9 REFRESH_TOKENS

```python
class RefreshTokenOut(BaseModel):
    id: int
    user_id: int
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**Decision:** No `RefreshTokenCreate`, and no route ever returns `RefreshTokenOut` as part of a login/refresh response body. Like `COMPANIES` and `GENERATED_EMAILS`, this entity is populated as a side effect (of login or token refresh), not a direct user-facing create. `RefreshTokenOut` deliberately excludes `token_hash` entirely — the same allowlist principle that keeps `UserOut` from ever exposing `password_hash` in §2.1. This schema exists for potential internal/debug use (e.g. a future "list my active sessions" feature), not for the actual login/refresh response, which will need its own `TokenPairOut`-style schema (`access_token`, `refresh_token`, `token_type`) carrying the raw token values — that schema is built at auth-implementation time, not decided here.

**Reasoning:** Added during Phase 1 planning as a direct consequence of the JWT auth-flow decision (see `OPEN_QUESTIONS.md`'s "Resolved" section): the refresh token is deliberately an opaque random string, not a JWT, so it can be revoked before its natural expiry — logout only works if something persists to revoke. `token_hash` (not the raw token) is what's stored, mirroring the same reasoning as `UserCreate.password` vs. the ORM's `password_hash` column in §2.1 — never persist a secret in a form that's directly usable if the row leaks. `token_hash` carries a unique index for the same lookup-performance reasoning as `Company.domain` in `ARCHITECTURE.md` §5 — the refresh endpoint looks a presented token up by its hash on every call.

---

## 3. Alembic Migration Plan

### 3.1 Single initial migration

**Decision:** All 9 tables are created in one initial migration, not split into one migration per table.

**Reasoning:** The general Alembic convention (one migration per logical change) exists to track incremental schema discovery over time. That doesn't apply here — the schema was fully locked (all entities, relationships, and field-level decisions above) before any migration is written. Splitting into 9 migrations would re-enact a design process that's already finished.

`REFRESH_TOKENS` (added during Phase 1 planning, after the original seven entities were locked) is still included in this same initial migration rather than treated as a later addition. The distinction that matters isn't *when* a table was decided, it's whether it was fully decided before the migration file gets written — `REFRESH_TOKENS`' schema was locked before any migration exists, exactly like the original seven; it just wasn't locked at the same moment they were.

**Where multiple migrations remain correct:** Genuinely later, uninformed-at-this-point additions — e.g. the deferred `SEARCHES` table from the product doc's deferred-features list — since that decision, by design, comes only after real usage informs whether it's needed.

### 3.2 Naming convention

**Decision:** An explicit `NAMING_CONVENTION` dict is set on `MetaData` in `app/db/base.py` before any migration is generated:

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)
```

**Reasoning:** Without this, Postgres/SQLAlchemy auto-generates constraint names that aren't guaranteed consistent across environments. A future hand-written migration (e.g. dropping a constraint) needs a predictable name to reference rather than one that has to be looked up directly in the database.

### 3.3 `env.py` setup

**Decision:** `target_metadata = Base.metadata` (with every model imported into `db/base.py` so autogenerate can see them), and the database URL is read from `settings` (`pydantic-settings`/env var) rather than hardcoded in `alembic.ini`.

**Reasoning:** `target_metadata` is what makes `alembic revision --autogenerate` possible at all. Reading the URL from settings matters once more than one database exists (local dev vs. deployed) — hardcoding risks pointing the migration tool at the wrong one.

### 3.4 Postgres enum handling

**Decision:** For every enum persisted as a column (`VerificationTier` on `RAW_PROVIDER_RESULTS` and `CONTACTS`; `OutcomeEventType` on `OUTCOMES`), the migration's `upgrade()` explicitly creates the Postgres native enum type, and `downgrade()` explicitly drops it after dropping the dependent table(s):

```python
def upgrade():
    verification_tier = sa.Enum(
        "verified", "pattern_guessed", "catch_all", "unknown",
        name="verification_tier"
    )
    verification_tier.create(op.get_bind())
    # ... op.create_table(...)

def downgrade():
    op.drop_table("raw_provider_results")
    sa.Enum(name="verification_tier").drop(op.get_bind())
```

**Reasoning:** Postgres implements enums as a genuine native type, not a `VARCHAR` with a constraint. `downgrade()` dropping the table does *not* drop the type — re-running `upgrade()` after a `downgrade()` without the explicit `drop()` fails with "type already exists." Autogenerate sometimes misses this in the generated `downgrade()`, so it must be manually checked, not trusted blindly.

**Note:** `ProviderStatus` (see `ARCHITECTURE.md` §4.4) is *not* one of these — it's a transient orchestration signal inside `contact_discovery.py`, never written to a column, so it has no migration footprint. `REFRESH_TOKENS` has no enum columns either — it's untouched by this section.

### 3.5 JSON columns use `JSONB`, not `JSON`

**Decision:** All JSON-shaped columns — `raw_response` (`RAW_PROVIDER_RESULTS`), `eval_breakdown` and `match_data` (`GENERATED_EMAILS`), and `confidence_breakdown` (`CONTACTS`) — use Postgres's `JSONB` type.

**Reasoning:** `JSON` stores an exact text copy (preserving formatting/key order) and re-parses on every read. `JSONB` stores a decomposed binary format — no formatting preserved, but indexable and faster to query. None of these columns need exact-formatting preservation, and some (e.g. `match_data`) may plausibly need to be queried into later for debugging/analytics. No scenario in this schema favors plain `JSON`. `REFRESH_TOKENS` has no JSON-shaped columns and is unaffected by this decision.

### 3.6 Foreign keys require explicit indexing

**Decision:** Every foreign key column is declared with `index=True` at the model level: `resumes.user_id`, `refresh_tokens.user_id`, `job_descriptions.company_id`, `raw_provider_results.company_id`, `contacts.company_id`, `generated_emails.contact_id/resume_id/job_description_id`, `outcomes.generated_email_id`.

**Reasoning:** Postgres automatically indexes primary keys and `unique=True` columns, but **not** foreign key columns. Columns like `generated_emails.contact_id` will be queried constantly (fetching a contact's emails, analytics joins) — without an explicit index, that's a sequential scan as tables grow. Autogenerate mirrors exactly what the SQLAlchemy models specify, so this must be decided at the model layer, not patched into the migration afterward.

### 3.7 Migration workflow

1. Write all 9 model files in `app/models/`, with `index=True` on every FK and `JSONB` on every JSON-shaped column decided upfront.
2. `alembic revision --autogenerate -m "initial schema"`.
3. **Manually review before running:** enum `drop()` calls present in `downgrade()`, every FK column indexed, `JSONB` (not `JSON`) picked up correctly, table creation order matches the dependency graph (`USERS`/`COMPANIES` first, `OUTCOMES` last).
4. `alembic upgrade head` against local Postgres.
5. Sanity check with `\d+ <table>` in `psql` to confirm enum types, JSONB columns, and FK indexes actually exist rather than assuming the generated file is correct.

### 3.8 Entity dependency order

```
USERS ─────────────┐
                    ├──> RESUMES
                    ├──> REFRESH_TOKENS
COMPANIES ──────────┼──> JOB_DESCRIPTIONS
                    ├──> RAW_PROVIDER_RESULTS
                    └──> CONTACTS
                              │
RESUMES + JOB_DESCRIPTIONS + CONTACTS ──> GENERATED_EMAILS
                                                  │
                                          GENERATED_EMAILS ──> OUTCOMES
```

Autogenerate performs this topological sort automatically via foreign keys; it isn't hand-ordered. Worth understanding independently so an incorrect autogenerate diff is recognizable rather than assumed correct.
