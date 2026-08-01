# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-01 — LLM extraction slice (`app/llm/` + `extraction.py` + extract endpoints). Full suite: `pytest` → **93 passed** against real Postgres (transaction-rollback `conftest.py`; Anthropic SDK fully mocked — no live LLM credits).*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Postgres via Docker Compose** — `docker-compose.yml` at repo root, `postgres:18`, volume mounted at `/var/lib/postgresql` (not `.../data` — the 18+ layout requirement). Container runs cleanly.
- **`backend/alembic/versions/bd31568efd53_initial_schema.py`** — applied successfully (`alembic upgrade head` ran with no errors against the real DB). Independently reviewed against `DATA_MODEL.md` §3.4–§3.8. **9 tables**.
- **`backend/alembic/versions/97807b9a3c89_add_user_id_to_job_descriptions.py`** — additive migration adding `JOB_DESCRIPTIONS.user_id`. Confirmed applied.
- **`app/core/config.py`, `app/db/base.py`, `app/db/session.py`** — settings-sourced DB URL, JWT, CORS, `contact_provider` / `hunter_api_key`, plus new LLM settings: `anthropic_api_key`, `llm_model` (default `claude-haiku-4-5`), `llm_max_retries` (default `1`). `.env.example` updated.
- **`app/core/enums.py`** — shared `VerificationTier`/`OutcomeEventType` in a neutral location.
- **9 SQLAlchemy models** — FK columns only, no ORM `relationship()` associations.
- **`app/core/security.py`** — **Verified:** `pytest tests/core/test_security.py` — **9 passed**.
- **Auth Pydantic schemas** — `app/schemas/user.py`, `app/schemas/auth.py`.
- **`app/core/exceptions.py`** — `AppException` hierarchy including `ConflictError` (409) and new `LLMExtractionError` (502). Handler returns `{user_message, error_code}`.
- **`app/core/deps.py`** — `get_current_user` / `get_db` exercised via HTTP auth tests.
- **Auth service + router + `main.py` wiring** — **Verified:** `pytest tests/routers/test_auth.py` — **14 passed**.
- **Resume schemas + service + router** — upload/list/detail unchanged; plus new `POST /resumes/{resume_id}/extract`. **Verified (prior + extract):** resume router/service suites still green; extract covered below.
- **Job-description schemas + service + router** — create unchanged; `get_job_description_by_id` now filters on `id` + `user_id` (ownership, same as resumes); plus new `POST /job-descriptions/{jd_id}/extract`. **Verified:** create suite still green; extract covered below.
- **MockProvider-backed contact discovery pipeline** — **Verified:** `pytest tests/services/test_contact_discovery.py` — **8 passed**.
- **HunterProvider** — **Verified:** `pytest tests/providers/test_hunter_provider.py` — **12 passed** (HTTP mocked).
- **Company name resolution (Clearbit)** — **Verified:** `pytest tests/services/test_company_resolution.py tests/routers/test_company_resolution.py` — **7 passed** (5 service + 2 router).
- **LLM layer — shared client + structured extraction (this session):**
  - **`app/llm/client.py`** — `LLMClient` wrapping `AsyncAnthropic`. `async complete(prompt, response_schema) -> BaseModel`: calls Messages API, parses JSON (strips optional markdown fences), validates with the given Pydantic schema, retries up to `settings.llm_max_retries` on parse/validation failure (feeds prior raw response + error back as a correction turn), raises `LLMExtractionError` (502) if retries exhausted or the Anthropic call fails. Model / retry count / API key from `Settings` — not hardcoded. Extraction services never import the Anthropic SDK.
  - **`app/llm/prompts.py`** — prompt templates for resume → `ResumeExtraction` and JD → `JDExtraction` (schemas reused from `app/schemas/`, not redefined).
  - **`app/services/extraction.py`** — `async extract_resume(db, resume_id, user_id)` / `async extract_job_description(db, jd_id, user_id)`: ownership-filtered fetch via existing helpers, `LLMClient.complete`, persist `extracted_data` (overwrite on re-run), commit, return row. Optional `llm_client=` for tests.
  - **Routers** — `POST /resumes/{resume_id}/extract` → `ResumeOut`; `POST /job-descriptions/{jd_id}/extract` → `JobDescriptionOut`; both behind `get_current_user`. Idempotent retry = call again.
  - **Verified:**
    - `pytest tests/llm/test_client.py` — **5 passed** (success; one retry-then-success; retry-exhausted → `LLMExtractionError`; markdown-fenced JSON; missing API key). Anthropic mocked via `unittest.mock` on `AsyncAnthropic` — no live calls.
    - `pytest tests/services/test_extraction.py` — **8 passed** (resume + JD: happy path, wrong-owner → `NotFoundError`, missing id → `NotFoundError`, re-extraction overwrites). `LLMClient` injected/mocked; `asyncio.run` (no `pytest-asyncio`).
    - `pytest tests/routers/test_extraction.py` — **6 passed** (resume + JD: happy path 200 with `extracted_data`, unauthenticated → 401, wrong owner → 404).
- **Integration test harness** — `backend/tests/conftest.py` + real Postgres nested transactions.
- **`backend/requirements.txt`** — adds `anthropic==0.120.2`. No `pytest-asyncio` / `respx`.

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite (covered at service layer + Hunter unit tests).

### Not started

- **`app/services/matching.py`** — match/gap analysis (`ResumeExtraction` × `JDExtraction` → `MatchData`). Immediate next LLM task; see `ARCHITECTURE.md` §3 / `OPEN_QUESTIONS.md` Resolved.
- **Email generation + eval** — `email_generation.py` / `eval.py` not started.
- **Remaining real contact providers** — `ApolloProvider` / `AnymailProvider` deferred.
- **Frontend** — scaffolded only (Vite + React + TS).
- **Refresh-token rotation / reuse-detection**, **cookie-based refresh transport**, **login rate-limiting** — deferred in `OPEN_QUESTIONS.md`.

---

## Deviations from `ARCHITECTURE.md` / `DATA_MODEL.md`

*Things a future session would get wrong by trusting the original docs literally, without this note.*

1. **Enum location resolved concretely as `app/core/enums.py`.**
2. **`db/base.py` uses SQLAlchemy 2.0's `DeclarativeBase` class**, not the `declarative_base(...)` function call shown in `DATA_MODEL.md` §3.2.
3. **Model registration for Alembic lives in `alembic/env.py`**, not the bottom of `app/db/base.py`.
4. **`extracted_data`** (on `RESUMES` and `JOB_DESCRIPTIONS`) **is JSONB**, though `DATA_MODEL.md` §3.5's explicit list omits it.
5. **DB-level unique constraints** — trust the migration file, not Pydantic schemas, for constraints.
6. **Table count corrected** to **9**.
7. **Auth crypto choices locked in code:** bcrypt directly (not passlib); refresh tokens SHA-256; access TTL 30m / refresh TTL 30d; PyJWT.
8. **`TokenPairOut`** in `app/schemas/auth.py`.
9. **`AppException` handler client key is `user_message`**, not `detail`.
10. **Resume upload parsing / limits:** pypdf / python-docx; 2MB cap; min 50 chars extracted text.
11. **`JOB_DESCRIPTIONS.user_id`** via migration `97807b9a3c89` — live model/API have it even if an older `DATA_MODEL.md` §2.3 snippet omitted it.
12. **Confidence score formula** — unvalidated v1 weights in `contact_discovery.py` (see prior session notes).
13. **Discovery HTTP path is `POST /contacts/discover`.**
14. **`ContactDiscoveryRequest` lives in `app/schemas/contact.py`.**
15. **`ProviderSearchResult.candidates` uses `Field(default_factory=list)`.**
16. **Phase 1 real-provider gap** was closed later by HunterProvider; MockProvider-first orchestration shipped first.
17. **Clearbit timeout = 5.0s.**
18. **Company-resolution router** at `POST /companies/search`.
19. **`POST /companies/search` requires auth.**
20. **Clearbit HTTP mocking uses `unittest.mock`**, not `respx`.
21. **`tests/services/__init__.py` and `tests/routers/__init__.py`** for same-basename collection.
22. **Hunter → VerificationTier mapping** — unvalidated v1 heuristic in `hunter.py`.
23. **Hunter tier-matching** — case-insensitive substring of `position`.
24. **`CONTACT_PROVIDER` settings flag** (`mock`/`hunter`, default `mock`).
25. **Hunter credit-conservation cache** is instance-local, in-process, keyed by `company_domain`.
26. **LLM extraction implementation choices locked this session (not previously numeric in the docs):**
    - **Default model:** `claude-haiku-4-5` — cost-appropriate for structured extraction; not Sonnet/Opus.
    - **`llm_max_retries` default `1`** — one correction retry after the first parse/validation failure (two attempts total).
    - **`LLMExtractionError.status_code = 502`** — same class of "upstream dependency failed" as `ProviderUnavailableError`.
    - **`LLMClient.complete` is `async`** and uses `AsyncAnthropic` (signature deviation from a sync sketch; matches the rest of the async external-IO style).
    - **`max_tokens=4096`** hardcoded on the client for extraction-sized payloads (not a Settings field).
    - **`get_job_description_by_id(db, user, jd_id)`** now ownership-filters on `user_id` (was id-only); required once extract became a read path returning `raw_text`.

27. **`extraction.py`'s `_user_for_id` helper introduces an avoidable extra DB query per extraction call — accepted as minor debt, not fixed.** Both `/extract` routers already receive a full `User` object via `get_current_user`, but pass only `current_user.id` into `extraction_service.extract_resume`/`extract_job_description`, which then re-fetches that same row via `_user_for_id` just to satisfy `get_resume_by_id`/`get_job_description_by_id`'s existing `User`-object signature. Cost is one extra indexed PK lookup per extraction call — real but trivial at this scale, not a correctness issue. Deferred rather than fixed now because, unlike the rate-limit-retry asymmetry above, this isn't a real design tradeoff — the fix is unambiguous and low-risk (accept `current_user: User` directly in both `extraction.py` functions, drop `_user_for_id`, update both router call sites to pass `current_user` instead of `current_user.id`), just not worth a Cursor round-trip on the current timeline. Revisit opportunistically next time `extraction.py` is touched for another reason (e.g. when `matching.py` is built and needs the same ownership-check pattern — a natural moment to fix both at once).

---

## What's next

1. **`app/services/matching.py`** — match/gap analysis producing `MatchData` from a `ResumeExtraction` + `JDExtraction` (dedicated service per `ARCHITECTURE.md` §3). Immediate next LLM task; then email generation + eval.
2. **Frontend** — thin end-to-end flow: company resolution → discovery → resume/JD upload → extract → generated email.
3. **Stretch, only if time remains:** Apollo/Anymail, outcome-logging polish, basic analytics view.

---

## Doc notes from this session

- **`DATA_MODEL.md`:** no edit. `ResumeOut` / `JobDescriptionOut` already expose `extracted_data` and are sufficient as extract-endpoint response models — nothing built here is inconsistent with the locked schemas.
- **`product_discovery_summary.md`:** Phase 3 updated — extraction is a user-triggered slice ahead of match/gap, not "LLM layer still fully unbuilt."
- **`ARCHITECTURE.md` §3 / `OPEN_QUESTIONS.md` Resolved:** updated for four LLM services (`matching.py`) and the extraction-trigger decision.
