# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-01 — GENERATED_EMAILS persistence + `POST /generated-emails` endpoint (`generated_emails.py` orchestrator + `GenerateEmailRequest` / `GeneratedEmailOut` schemas). Full generate→evaluate→persist loop is HTTP-callable end to end for the first time. Full suite: `pytest` → **117 passed** against real Postgres (transaction-rollback `conftest.py`; Anthropic SDK / LLM services fully mocked — no live LLM credits). Actual terminal line: `117 passed, 63 warnings in 19.76s`.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **GENERATED_EMAILS persistence + generation endpoint (this session):**
  - **Model verified:** `app/models/generated_email.py` columns match `GeneratedEmailOut` exactly (`contact_id`, `resume_id`, `job_description_id`, `subject`, `body`, `eval_score`, `eval_breakdown` JSONB, `match_data` JSONB, `gate_passed`, `created_at`) — no migration needed.
  - **`app/schemas/generated_email.py`** — added `GenerateEmailRequest` + `GeneratedEmailOut` (existing `EmailDraft` / `MatchData` / `Eval*` unchanged).
  - **`app/services/generated_emails.py`** — `generate_and_persist_email(db, current_user, contact_id, resume_id, job_description_id)`: ownership-filtered resume/JD load → existence-only contact load → require extractions → company FK load + company/contact consistency check → `generate_match_data` → `generate_email` → `evaluate_with_retry` → compute `eval_score` (plain mean of five dimensions) + `gate_passed` → always INSERT new row → commit/refresh/return. Cheap checks before any LLM call.
  - **Router** — `POST /generated-emails` (auth required), `response_model=GeneratedEmailOut`, thin wrapper wired in `main.py`.
  - **Verified:** `pytest tests/services/test_generated_emails.py` — **8 passed** (happy path + eval_score average math; wrong-owner resume/JD → NotFoundError; missing contact → NotFoundError; missing extractions → ValidationError; company mismatch → ValidationError; same triple → two distinct rows). `tests/routers/test_generated_emails.py` — **3 passed** (401 without token; 200 + `GeneratedEmailOut` shape; 404 on bad ids). Service tests use real Postgres; LLM sub-calls monkeypatched. Router tests mock the service layer.
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
- **LLM layer — shared client + structured extraction:**
  - **`app/llm/client.py`** — `LLMClient` wrapping `AsyncAnthropic`. `async complete(prompt, response_schema) -> BaseModel`.
  - **`app/llm/prompts.py`** — resume/JD extraction + matching + email/eval/refine prompts.
  - **`app/services/extraction.py`** — `extract_resume` / `extract_job_description` with optional `llm_client=`.
  - **Routers** — `POST /resumes/{resume_id}/extract` → `ResumeOut`; `POST /job-descriptions/{jd_id}/extract` → `JobDescriptionOut`.
  - **Verified:** `pytest tests/llm/test_client.py` — **5 passed**; `tests/services/test_extraction.py` — **8 passed**; `tests/routers/test_extraction.py` — **6 passed**.
- **LLM layer — match/gap analysis:**
  - **`app/schemas/generated_email.py`** — `SkillMatch`, `ExperienceAlignment`, `MatchData` (plus email/eval/`GeneratedEmailOut` schemas).
  - **`app/llm/prompts.py`** — `matching_prompt(resume_extraction, jd_extraction)`.
  - **`app/services/matching.py`** — `async generate_match_data(...) -> MatchData`. No DB session, no router.
  - **Verified:** `pytest tests/services/test_matching.py` — **3 passed**.
- **LLM layer — email generation + eval (prior session):**
  - **`app/schemas/generated_email.py`** — `EmailDraft`, full eval stack (`EvalGates` with `violation_detail`, `EvalDimensions`, `EvalBreakdown`, `EvalResult`).
  - **`app/services/email_generation.py`** — `async generate_email(...) -> EmailDraft`. No DB.
  - **`app/services/eval.py`** — `evaluate_email` / `refine` / `evaluate_with_retry` (silent single-retry gate loop).
  - **Verified:** `pytest tests/services/test_email_generation.py` — **4 passed**; `tests/services/test_eval.py` — **6 passed**.
- **Integration test harness** — `backend/tests/conftest.py` + real Postgres nested transactions.
- **`backend/requirements.txt`** — includes `anthropic==0.120.2`. No `pytest-asyncio` / `respx`.

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite (covered at service layer + Hunter unit tests).

### Not started

- **Remaining real contact providers** — `ApolloProvider` / `AnymailProvider` deferred.
- **Frontend** — scaffolded only (Vite + React + TS). Immediate next focus.
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
27. **`extraction.py`'s `_user_for_id` helper introduces an avoidable extra DB query per extraction call — accepted as minor debt, not fixed.** Prior note suggested revisiting when `matching.py` was built; that trigger did not apply — `matching.py` takes already-extracted Pydantic objects and never touches the DB / ownership helpers. `generated_emails.py` also takes `current_user: User` directly (does not repeat the `_user_for_id` pattern). Fix remains: accept `current_user: User` directly in both `extraction.py` functions, drop `_user_for_id`, update both router call sites. Revisit opportunistically next time `extraction.py` is touched for another reason.
28. **Match/gap analysis implementation choices locked previously:**
    - **`MatchData` / `SkillMatch` / `ExperienceAlignment` live in `app/schemas/generated_email.py`** — file name matches the persistence home (`GENERATED_EMAILS.match_data`).
    - **`matching_prompt` serializes both extractions via `model_dump_json(indent=2)`** inside fenced JSON blocks, and embeds `MatchData.model_json_schema()` the same way extraction prompts do.
    - **No dedicated match/gap HTTP endpoint** — deliberate; see `OPEN_QUESTIONS.md` Resolved. Product surfacing is via `match_data` on `GeneratedEmailOut`.
    - **`generate_match_data` does not check `extracted_data is not None`** — that check lives in `generated_emails.py` (the DB-loading caller).
29. **`EvalGates.violation_detail` added after the original schema lock.** Free-form `str | None` (not a fixed violation-type enum), populated only when a Tier 1 gate fails, solely to feed `refine()`'s feedback argument. Never shown to the user; not persisted independently (rides inside `eval_breakdown` JSONB). Documented in `DATA_MODEL.md` §2.7 and `OPEN_QUESTIONS.md` Resolved.
30. **`EmailDraft` is a non-persisted schema** (`subject` + `body`) for generation/refine LLM I/O. Separate from `GeneratedEmailOut` so ephemeral draft shapes aren't conflated with the persisted API response.
31. **`generate_email` / `evaluate_email` take explicit primitives** (`contact_name`, `contact_title`, `company_name`, `role_title` as needed) plus `MatchData` / `EmailDraft` — not ORM/DB objects, no DB session. Ownership/loading lives in `generated_emails.py`.
32. **`evaluate_with_retry` owns gate-retry orchestration inside `eval.py`**, not a separate module and not the router. `refine` stays the standalone reusable primitive for the product doc's v1.1+ multi-turn path. On gate failure with a missing `violation_detail`, a short fallback feedback string is used so `refine` always receives `str`.
33. **`contact_name=None` fallback handling is explicit in both prompts:** generation instructs a generic professional greeting and forbids fabricating a name; eval treats that generic greeting as a pass for `correct_contact_name_used` when `contact_name` is null.
34. **`eval_prompt` / `evaluate_email` / `evaluate_with_retry` gained `company_name` + `role_title` before commit.** Gap in the original task spec (generation already had them; eval didn't) — caught in review, not a Cursor deviation. Needed so `role_company_specificity` grades accuracy against trusted DB ground truth. `refine()` deliberately left unchanged (`email` + `feedback` only).
35. **`app/services/generated_emails.py` is a separate orchestrating service from `email_generation.py`.** `email_generation.py` stays a pure LLM call site (primitives in → `EmailDraft` out, no DB) per ARCHITECTURE.md §3's four-LLM-services table. Persistence, ownership checks, company consistency, score aggregation, and insert live in `generated_emails.py` — same "thick service, thin router" pattern as `contact_discovery.py`. Not a fifth LLM call site; §3's table is unchanged.
36. **Always-insert-never-overwrite on `GENERATED_EMAILS`.** Deliberate divergence from `extraction.py`'s overwrite-in-place: each regeneration produces a new row so future `OUTCOMES` FKs remain valid. Same `(contact_id, resume_id, job_description_id)` → multiple rows is expected.
37. **`eval_score` is the plain unweighted average of the five `EvalDimensions` ints**, always computed regardless of `gate_passed`. No zeroing/omitting on gate failure; gates are a separate boolean column.
38. **Company/contact consistency check** — server rejects with `ValidationError` when `contact.company_id != job_description.company_id`. Defense-in-depth; frontend filtering is a Phase 3 forward note (see `OPEN_QUESTIONS.md`).

---

## What's next

1. **Frontend** — thin end-to-end flow: company resolution → discovery → resume/JD upload → extract → generated email. Highest remaining risk; only piece left before the app itself is demoable.
2. **Stretch, only if time remains:** Apollo/Anymail, outcome-logging polish, basic analytics view.

---

## Doc notes from this session

- **`DATA_MODEL.md` §2.7:** added `GenerateEmailRequest` — real gap filled (doc previously only had `GeneratedEmailOut` + "no GeneratedEmailCreate"); updated persistence wording for `EmailDraft` / `violation_detail` now that the row is written.
- **`ARCHITECTURE.md` §2:** cited `generated_emails.py` alongside `contact_discovery.py` as a thick-service example. No §3 change (not a fifth LLM call site).
- **`OPEN_QUESTIONS.md`:** three new Resolved entries (company/contact consistency, `eval_score` formula, always-insert); one new "Not yet discussed" (frontend company/contact filtering); past-tense updates on matching/eval Resolved entries that previously said "future generation endpoint."
- **`product_discovery_summary.md`:** Phase 3 updated — LLM loop is fully demoable via the API; frontend is the only remaining piece before the app itself is demoable.
