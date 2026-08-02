# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-01 — email generation + eval services slice (`email_generation.py` / `eval.py` + `EmailDraft` / eval schemas + generation/eval/refine prompts), including the pre-commit correction threading `company_name`/`role_title` through the eval path. Full suite: `pytest` → **106 passed** against real Postgres (transaction-rollback `conftest.py`; Anthropic SDK fully mocked — no live LLM credits). Actual terminal line: `106 passed, 59 warnings in 9.81s`.*

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
  - **`app/llm/prompts.py`** — resume/JD extraction prompts + matching + (this session) email/eval/refine prompts.
  - **`app/services/extraction.py`** — `extract_resume` / `extract_job_description` with optional `llm_client=`.
  - **Routers** — `POST /resumes/{resume_id}/extract` → `ResumeOut`; `POST /job-descriptions/{jd_id}/extract` → `JobDescriptionOut`.
  - **Verified:** `pytest tests/llm/test_client.py` — **5 passed**; `tests/services/test_extraction.py` — **8 passed**; `tests/routers/test_extraction.py` — **6 passed**.
- **LLM layer — match/gap analysis (prior session):**
  - **`app/schemas/generated_email.py`** — `SkillMatch`, `ExperienceAlignment`, `MatchData` (plus this session's email/eval schemas below).
  - **`app/llm/prompts.py`** — `matching_prompt(resume_extraction, jd_extraction)`.
  - **`app/services/matching.py`** — `async generate_match_data(...) -> MatchData`. No DB session, no router.
  - **Verified:** `pytest tests/services/test_matching.py` — **3 passed**.
- **LLM layer — email generation + eval (this session):**
  - **`app/schemas/generated_email.py`** — added `EmailDraft` (ephemeral subject/body), full eval stack (`EvalGates` with new `violation_detail`, `EvalDimensions`, `EvalBreakdown`, `EvalResult`). Deliberately omits `GeneratedEmailOut` — that belongs to the persistence/router task.
  - **`app/llm/prompts.py`** — `email_generation_prompt`, `eval_prompt`, `refine_prompt`. Embed structured inputs via `model_dump_json(indent=2)` and target schemas via `model_json_schema()`. Generation prompt: select ≤2–3 strongest points, never claim `unmatched_jd_requirements`, use `overall_match_summary` as framing, explicit `contact_name=None` → generic greeting (never fabricate). Eval prompt: Tier 1 gates + Tier 2 1–5 dimensions; takes `company_name`/`role_title` as trusted ground truth for `role_company_specificity` (explicitly excluded from `no_unsupported_claims`); `violation_detail` required when any gate fails.
  - **`app/services/email_generation.py`** — `async generate_email(contact_name, contact_title, company_name, role_title, match_data, *, llm_client=None) -> EmailDraft`. Same shape as `matching.py`: injectable client, no DB, `LLMExtractionError` propagates.
  - **`app/services/eval.py`** — `evaluate_email(..., company_name, role_title) → EvalResult`; `refine(email, feedback) -> EmailDraft` (unchanged minimal signature); `evaluate_with_retry` owns the silent single-retry gate loop (evaluate → on failure refine once with `violation_detail` → re-evaluate → return second pass either way). Constructs at most one `LLMClient` and reuses it across calls.
  - **Verified:** `pytest tests/services/test_email_generation.py` — **4 passed**; `tests/services/test_eval.py` — **6 passed** (happy paths + schema args; prompt includes company/role + ground-truth / gate-scope instructions; `contact_name=None` fallback instructions; `LLMExtractionError` propagation; gate-pass skips refine; gate-fail calls judge → refine(feedback=`violation_detail`) → judge again). No DB fixture.
- **Integration test harness** — `backend/tests/conftest.py` + real Postgres nested transactions.
- **`backend/requirements.txt`** — includes `anthropic==0.120.2`. No `pytest-asyncio` / `respx`.

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite (covered at service layer + Hunter unit tests).

### Not started

- **`GENERATED_EMAILS` persistence + generation router endpoint** — immediate next task: endpoint taking `{contact_id, resume_id, job_description_id}`, load/ownership-check those rows, call `generate_match_data` → `generate_email` → `evaluate_with_retry`, persist a `GENERATED_EMAILS` row, return `GeneratedEmailOut`. Services exist; the loop is not yet HTTP-callable or persisted.
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
28. **Match/gap analysis implementation choices locked previously:**
    - **`MatchData` / `SkillMatch` / `ExperienceAlignment` live in `app/schemas/generated_email.py`**, even though `GeneratedEmailOut` itself is not built yet — file name matches the eventual persistence home (`GENERATED_EMAILS.match_data`) rather than inventing a `match.py` schema module.
    - **`matching_prompt` serializes both extractions via `model_dump_json(indent=2)`** inside fenced JSON blocks, and embeds `MatchData.model_json_schema()` the same way extraction prompts do — keeps the structured-output contract consistent across LLM call sites.
    - **No dedicated match/gap HTTP endpoint** — deliberate; see `OPEN_QUESTIONS.md` Resolved. Product surfacing happens later via `match_data` on the generated-email response.
    - **`generate_match_data` does not check `extracted_data is not None`** — that check belongs to the future caller that loads DB rows (now the generation router task, not `email_generation.py` itself — see #31).
29. **`EvalGates.violation_detail` added after the original schema lock.** Free-form `str | None` (not a fixed violation-type enum), populated only when a Tier 1 gate fails, solely to feed `refine()`'s feedback argument. Never shown to the user; not persisted independently. Documented in `DATA_MODEL.md` §2.7 and `OPEN_QUESTIONS.md` Resolved.
30. **`EmailDraft` is a new non-persisted schema** (`subject` + `body`) for generation/refine LLM I/O. Separate from `GeneratedEmailOut` (still deferred) so ephemeral draft shapes aren't conflated with the persisted API response.
31. **`generate_email` / `evaluate_email` take explicit primitives** (`contact_name`, `contact_title`, `company_name`, `role_title` as needed) plus `MatchData` / `EmailDraft` — not ORM/DB objects, no DB session, no re-pass of raw resume/JD extractions (`match_data` is already the condensed signal). Ownership/loading deferred to the next (router) task.
32. **`evaluate_with_retry` owns gate-retry orchestration inside `eval.py`**, not a separate module and not the future router. `refine` stays the standalone reusable primitive for the product doc's v1.1+ multi-turn path. On gate failure with a missing `violation_detail`, a short fallback feedback string is used so `refine` always receives `str` (defensive; the judge prompt requires `violation_detail` when a gate fails).
33. **`contact_name=None` fallback handling is explicit in both prompts:** generation instructs a generic professional greeting and forbids fabricating a name; eval treats that generic greeting as a pass for `correct_contact_name_used` when `contact_name` is null.
34. **`eval_prompt` / `evaluate_email` / `evaluate_with_retry` gained `company_name` + `role_title` before commit.** Gap in the original task spec (generation already had them; eval didn't) — caught in review, not a Cursor deviation. Needed so `role_company_specificity` grades accuracy against trusted DB ground truth, not just specific-sounding language. Prompt explicitly scopes `no_unsupported_claims` to candidate-fit / `match_data` claims so company/role references aren't false-flagged. `refine()` deliberately left unchanged (`email` + `feedback` only); the second `evaluate_with_retry` pass re-checks against full context including this ground truth.

---

## What's next

1. **`GENERATED_EMAILS` persistence + generation router endpoint** — authenticated endpoint taking `{contact_id, resume_id, job_description_id}`: load and ownership-check those rows (ensure extractions exist), call `generate_match_data` → `generate_email` → `evaluate_with_retry`, persist a `GENERATED_EMAILS` row (`subject`/`body`/`match_data`/`eval_breakdown`/`eval_score`/`gate_passed`), return `GeneratedEmailOut`. This is what makes the LLM loop demoable end to end.
2. **Frontend** — thin end-to-end flow: company resolution → discovery → resume/JD upload → extract → generated email.
3. **Stretch, only if time remains:** Apollo/Anymail, outcome-logging polish, basic analytics view.

---

## Doc notes from this session

- **`DATA_MODEL.md` §2.7:** added `EmailDraft`; added `violation_detail` to `EvalGates` with Decision/Reasoning (deliberate revision; free-form vs enum; refine-feedback-only).
- **`ARCHITECTURE.md` §3:** removed `*(future)*` from `email_generation.py` / `eval.py`; noted `evaluate_with_retry` owns single-retry orchestration and `refine` remains the reusable primitive.
- **`OPEN_QUESTIONS.md`:** four new Resolved entries — `violation_detail`, retry orchestration location, service input shape, `contact_name=None` fallback.
- **`product_discovery_summary.md`:** Phase 3 updated — LLM services functionally complete; persistence + router remain before the loop is demoable. Not overstated as done.
