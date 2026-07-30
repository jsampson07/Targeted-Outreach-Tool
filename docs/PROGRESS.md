# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-07-29 — verified via actual `backend/` file listing (`ls -R`), the applied Alembic migration (independently reviewed line-by-line against `DATA_MODEL.md` §3), and a successful `alembic upgrade head` against a running local Postgres container. Where something is known only from Cursor's own self-report and hasn't actually been exercised (no server run, no test written), that's called out explicitly below rather than stated as fact.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Postgres via Docker Compose** — `docker-compose.yml` at repo root, `postgres:18`, volume mounted at `/var/lib/postgresql` (not `.../data` — the 18+ layout requirement). Container runs cleanly.
- **`backend/alembic/versions/bd31568efd53_initial_schema.py`** — applied successfully (`alembic upgrade head` ran with no errors against the real DB). Independently reviewed against `DATA_MODEL.md` §3.4–§3.8: enum `create()`/`drop()` handled correctly (`create_type=False` + explicit type management, since `verification_tier` is shared across `contacts` and `raw_provider_results`), all FK columns indexed, all 4 required JSONB columns correct plus `extracted_data` as a reasonable extension (see Deviations), dependency order valid, no forward references. **9 tables**, not 7 or 8 — the earlier miscount in `DATA_MODEL.md`/`product_discovery_summary.md` has been corrected.
- **`app/core/config.py`, `app/db/base.py`, `app/db/session.py`** — functionally confirmed: `alembic/env.py` importing `get_settings()` and `Base.metadata` and successfully connecting to Postgres via the settings-sourced `DATABASE_URL` is real, executed proof these are wired correctly, not just present.
- **`app/core/enums.py`** — shared `VerificationTier`/`OutcomeEventType` enums in a neutral location, per `ARCHITECTURE.md` §4.4. Confirmed indirectly: the migration's native Postgres enum types were generated from these definitions without duplication errors, which wouldn't have worked if two separate enum classes existed.
- **9 SQLAlchemy models** (`app/models/`: `user.py`, `resume.py`, `job_description.py`, `company.py`, `raw_provider_result.py`, `contact.py`, `generated_email.py`, `outcome.py`, `refresh_token.py`) — schema-level correctness confirmed via the migration matching `DATA_MODEL.md` §2 field-for-field. **Not confirmed:** whether ORM-level `relationship()` associations were added between models (migrations don't require these, only FK columns — so their presence/absence hasn't been exercised by anything yet).

### Present, but not yet exercised by anything

- **`app/core/deps.py`, `app/core/exceptions.py`** — exist in the tree (these are the two files generated earlier in this chat, then manually placed into `app/core/`). Nothing has actually imported or called `get_db`, `get_current_user`, or raised an `AppException` yet — there are no routers to trigger them, so end-to-end execution is still unverified. However, `deps.py`'s field-name assumptions are now confirmed correct by direct inspection of `config.py`: `Settings.jwt_secret_key: str` and `Settings.jwt_algorithm: str = "HS256"` match exactly what `deps.py` references. Remaining gap is purely "never actually run," not "might be wrong."

### Not started

- **`app/main.py`** — confirmed empty (still the placeholder from the original `touch`). No `FastAPI()` app instance, no `CORSMiddleware`, no `AppException` handler registration yet — all three are already-decided work, just not yet written.
- **`app/schemas/`** — empty except `__init__.py`. None of the Pydantic API schemas from `DATA_MODEL.md` §2 (`UserCreate`/`UserOut`, `ContactDiscoveryRequest`, `TokenPairOut`, etc.) have been written yet.
- **`app/routers/`** — empty. No auth endpoints (signup/login/refresh/logout), no resume/JD upload, no discovery endpoint, nothing.
- **`app/services/`** — empty. No `contact_discovery.py`, no `email_generation.py`, no `eval.py`, no `company_resolution.py`.
- **`app/providers/`** — empty. `ContactProvider` ABC and `MockProvider` (the mock-first foundation `ARCHITECTURE.md` §4 is built around) don't exist yet.
- **`app/llm/`** — empty. No `client.py` wrapper, no `prompts.py`.
- **Auth logic itself** — no password hashing (passlib/bcrypt), no JWT issuing/validation, no refresh-token generation. The schema exists; none of the behavior does.
- **`tests/`** — empty except `__init__.py`. No tests written.
- **Frontend** — scaffolded only (Vite + React + TS template, confirmed running via `npm run dev`). No custom components, pages, or API calls built yet.

---

## Deviations from `ARCHITECTURE.md` / `DATA_MODEL.md`

*Things a future session would get wrong by trusting the original docs literally, without this note.*

1. **Enum location resolved concretely as `app/core/enums.py`.** `ARCHITECTURE.md` §4.4 said only "a neutral shared location" without naming a path. This is now the settled answer — import `VerificationTier`/`OutcomeEventType` from there, not from `models/` or `schemas/`.
2. **`db/base.py` uses SQLAlchemy 2.0's `DeclarativeBase` class**, not the `declarative_base(metadata=metadata)` function call shown literally in `DATA_MODEL.md` §3.2's example code. Functionally equivalent — same `NAMING_CONVENTION` dict applied — but that code block is now a stale-syntax reference, not copy-paste-accurate.
3. **`extracted_data`** (on `RESUMES` and `JOB_DESCRIPTIONS`) **is JSONB**, though `DATA_MODEL.md` §3.5 only explicitly lists `raw_response`, `eval_breakdown`, `match_data`, and `confidence_breakdown`. Reasonable extension of the same reasoning, not a conflict — but §3.5's list is technically incomplete now. Worth a one-line addendum to that doc; can do it on request.
4. **DB-level unique constraints not visible in `DATA_MODEL.md`'s Pydantic schemas** — `users.email`, `companies.domain` (already required by `ARCHITECTURE.md` §5), and `refresh_tokens.token_hash` (already called for in `DATA_MODEL.md` §2.9's own reasoning) are all enforced in the migration. Not a deviation, just a reminder: `DATA_MODEL.md`'s Pydantic classes were never meant to show DB constraints — **the migration file is the actual source of truth for DB-level constraints going forward**, not the schema doc.
5. **Table count corrected**: both `DATA_MODEL.md` and `product_discovery_summary.md` briefly said "8" after `REFRESH_TOKENS` was added; actual (and now corrected) count is **9**. Already fixed in both docs.

---

## What's next

Per the agreed Phase 1 build order (vertical slice, not horizontal layers) — **auth, end to end, is the immediate next piece**:

1. Password hashing (passlib/bcrypt) and JWT issuing/validation, matching the locked design (`OPEN_QUESTIONS.md`'s resolved JWT entry): access token stateless, refresh token opaque + DB-backed via the now-real `refresh_tokens` table.
2. `app/schemas/` — at minimum `UserCreate`/`UserOut` and a `TokenPairOut` (not yet defined anywhere, per `DATA_MODEL.md` §2.9's own note that it's "built at auth-implementation time").
3. `app/routers/auth.py` — signup, login, refresh, logout.
4. Wire `app/main.py` for real: instantiate the app, register the `AppException` handler, add `CORSMiddleware` — all previously decided, none yet built (confirmed empty).
5. First actual execution of `app/core/deps.py` (via a real protected route) — field names are already confirmed correct against `config.py`, so this is now just "run it," not "verify it."

Only after auth works end-to-end (signup → login → hit one protected route successfully): resume upload, then JD upload, then the first `MockProvider`-backed discovery call — same order agreed earlier, unchanged.
