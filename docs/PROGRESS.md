# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-01 — match/gap analysis slice (`matching.py` + `MatchData` schemas + `matching_prompt`). Full suite: `pytest` → **96 passed** against real Postgres (transaction-rollback `conftest.py`; Anthropic SDK fully mocked — no live LLM credits). Actual terminal line: `96 passed, 59 warnings in 10.22s`.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Postgres via Docker Compose** — `docker-compose.yml` at repo root, `postgres:18`, volume mounted at `/var/lib/postgresql` (not `.../data` — the 18+ layout requirement). Container runs cleanly.
- **`backend/alembic/versions/bd31568efd53_initial_schema.py`** — applied successfully (`alembic upgrade head` ran with no errors against the real DB). Independently reviewed against `DATA_MODEL.md` §3.4–§3.8. **9 tables**.
- **`backend/alembic/versions/97807b9a3c89_add_user_id_to_job_descriptions.py`** — additive migration adding `JOB_DESCRIPTIONS.user_id`. Confirmed applied.
- **`app/core/config.py`, `app/db/base.py`, `app/db/session.py`** — settings-sourced DB URL, JWT, CORS, `contact_provider` / `hunter_api_key`, plus LLM settings: `anthropic_api_key`, `llm_model` (default `claude-haiku-4-5`), `llm_max_retries` (default `1`). `.env.example` updated.
- **`app/core/enums.py`** — shared `VerificationTier`/`OutcomeEventType` in a neutral location.
- **9 SQLAlchemy models** — FK columns only, no ORM `relationship()` associations.
- **`app/core/security.py`** — **Verified:** `pytest tests/core/test_security.py` — **9 passed**.
- **Auth Pydantic schemas** — `app/schemas/user.py`, `app/schemas/auth.py`.
- **`app/core/exceptions.py`** — `AppException` hierarchy including `ConflictError` (409) and `LLMExtractionError` (502). Handler returns `{user_message, error_code}`.
- **`app/core/deps.py`** — `get_current_user` / `get_db` exercised via HTTP auth tests.
- **Auth service + router + `main.py` wiring** — **Verified:** `pytest tests/routers/test_auth.py` — **14 passed**.
- **Resume schemas + service + router** — upload/list/detail + `POST /resumes/{resume_id}/extract`.
- **Job-description schemas + service + router** — create + ownership-filtered `get_job_description_by_id` + `POST /job-descriptions/{jd_id}/extract`.
- **MockProvider-backed contact discovery pipeline** — **Verified:** `pytest tests/services/test_contact_discovery.py` — **8 passed**.
- **HunterProvider** — **Verified:** `pytest tests/providers/test_hunter_provider.py` — **12 passed** (HTTP mocked).
- **Company name resolution (Clearbit)** — **Verified:** `pytest tests/services/test_company_resolution.py tests/routers/test_company_resolution.py` — **7 passed** (5 service + 2 router).
- **LLM layer — shared client + structured extraction (prior session):**
  - **`app/llm/client.py`** — `LLMClient` wrapping `AsyncAnthropic`. `async complete(prompt, response_schema) -> BaseModel`.
  - **`app/llm/prompts.py`** — resume/JD extraction prompts + (this session) `matching_prompt`.
  - **`app/services/extraction.py`** — `extract_resume` / `extract_job_description` with optional `llm_client=`.
  - **Routers** — `POST /resumes/{resume_id}/extract` → `ResumeOut`; `POST /job-descriptions/{jd_id}/extract` → `JobDescriptionOut`.
  - **Verified:** `pytest tests/llm/test_client.py` — **5 passed**; `tests/services/test_extraction.py` — **8 passed**; `tests/routers/test_extraction.py` — **6 passed**.
- **LLM layer — match/gap analysis (this session):**
  - **`app/schemas/generated_email.py`** — `SkillMatch`, `ExperienceAlignment`, `MatchData` only (per `DATA_MODEL.md` §2.7). Deliberately omits `GeneratedEmailOut` / eval schemas — those belong to a later task.
  - **`app/llm/prompts.py`** — `matching_prompt(resume_extraction, jd_extraction)` embeds both extractions as JSON and instructs the model to check *every* JD skill/responsibility (complete comparison for eval's later ground-truth use, not a strongest-matches shortlist).
  - **`app/services/matching.py`** — `async generate_match_data(resume_extraction, jd_extraction, *, llm_client=None) -> MatchData`. Takes already-extracted Pydantic objects; no DB session, no router, no ownership/existence checks. Calls `LLMClient.complete(prompt, MatchData)` and returns the result directly; `LLMExtractionError` propagates unchanged.
  - **Verified:** `pytest tests/services/test_matching.py` — **3 passed** (happy path + `response_schema=MatchData`; prompt incorporates JD + resume fixture content; `LLMExtractionError` propagates). No DB fixture.
- **Integration test harness** — `backend/tests/conftest.py` + real Postgres nested transactions.
- **`backend/requirements.txt`** — includes `anthropic==0.120.2`. No `pytest-asyncio` / `respx`.

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite (covered at service layer + Hunter unit tests).

### Not started

- **Email generation + eval** — `email_generation.py` / `eval.py` not started. Immediate next LLM task is `email_generation.py` (which will call `generate_match_data`).
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
26. **LLM extraction implementation choices locked previously:**
    - **Default model:** `claude-haiku-4-5`.
    - **`llm_max_retries` default `1`** — one correction retry after the first parse/validation failure (two attempts total).
    - **`LLMExtractionError.status_code = 502`**.
    - **`LLMClient.complete` is `async`** and uses `AsyncAnthropic`.
    - **`max_tokens=4096`** hardcoded on the client.
    - **`get_job_description_by_id(db, user, jd_id)`** ownership-filters on `user_id`.
27. **`extraction.py`'s `_user_for_id` helper introduces an avoidable extra DB query per extraction call — accepted as minor debt, not fixed.** Prior note suggested revisiting when `matching.py` was built; that trigger did not apply — `matching.py` takes already-extracted Pydantic objects and never touches the DB / ownership helpers. Fix remains: accept `current_user: User` directly in both `extraction.py` functions, drop `_user_for_id`, update both router call sites. Revisit opportunistically next time `extraction.py` is touched for another reason.
28. **Match/gap analysis implementation choices locked this session:**
    - **`MatchData` / `SkillMatch` / `ExperienceAlignment` live in `app/schemas/generated_email.py`**, even though `GeneratedEmailOut` itself is not built yet — file name matches the eventual persistence home (`GENERATED_EMAILS.match_data`) rather than inventing a `match.py` schema module.
    - **`matching_prompt` serializes both extractions via `model_dump_json(indent=2)`** inside fenced JSON blocks, and embeds `MatchData.model_json_schema()` the same way extraction prompts do — keeps the structured-output contract consistent across LLM call sites.
    - **No dedicated match/gap HTTP endpoint** — deliberate; see `OPEN_QUESTIONS.md` Resolved. Product surfacing happens later via `match_data` on the generated-email response.
    - **`generate_match_data` does not check `extracted_data is not None`** — that check belongs to the future caller (`email_generation.py`) that loads DB rows.

---

## What's next

1. **`app/services/email_generation.py`** — grounded outreach draft from contact + match data (will call `generate_match_data`); then `eval.py` for the rubric-based quality check. Immediate next LLM task.
2. **Frontend** — thin end-to-end flow: company resolution → discovery → resume/JD upload → extract → generated email.
3. **Stretch, only if time remains:** Apollo/Anymail, outcome-logging polish, basic analytics view.

---

## Doc notes from this session

- **`DATA_MODEL.md`:** no edit. Built `SkillMatch` / `ExperienceAlignment` / `MatchData` match §2.7 exactly; `GeneratedEmailOut` / eval schemas correctly deferred.
- **`product_discovery_summary.md`:** MVP feature #4 clarified — match/gap analysis surfaces on the generated-email response, not as a separate earlier preview UI. Phase 3 updated to mark extraction + matching built, with `email_generation.py` / `eval.py` remaining.
- **`ARCHITECTURE.md` §3:** removed the `*(future)*` tag from `matching.py`. Left `email_generation.py` and `eval.py` tagged as future.
- **`OPEN_QUESTIONS.md`:** new Resolved entry — "Does `matching.py` get its own endpoint?" — documents the no-endpoint decision and the recompute/re-pay rationale. Also tightened the earlier "dedicated `matching.py` service" entry to reflect that it is now built.
