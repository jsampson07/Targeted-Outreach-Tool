# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-02 — backend `GET /generated-emails/{generated_email_id}` with join-based ownership + `violation_detail` API-boundary fix. Backend: pytest → **123 passed** (prior 120 + 3 new GET cases). Frontend suite unchanged this session (no frontend edits).*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **`GET /generated-emails/{generated_email_id}` (this session):**
  - Thin router endpoint, `response_model=GeneratedEmailOut`, auth required.
  - New helper `get_generated_email_by_id(db, user, generated_email_id)` — joins `GeneratedEmail` → `Resume` on `resume_id`, filters `GeneratedEmail.id` + `Resume.user_id == user.id`. No `user_id` on `GENERATED_EMAILS` (confirmed on the ORM model).
  - Relies on write-time invariant from `generate_and_persist_email` (resume + JD both ownership-filtered for the same user); does not re-verify that invariant at read time.
  - Missing and wrong-owner rows both → `NotFoundError` / 404 (non-distinguishing).
  - **`violation_detail` audit (pre-existing bug, fixed this session):** `GeneratedEmailOut` previously typed `eval_breakdown` as full internal `EvalBreakdown`/`EvalGates`, which would serialize judge refine text to the client on every Out response (including existing `POST /generated-emails`). Fixed via `EvalGatesOut` / `EvalBreakdownOut` (no `violation_detail`); `GeneratedEmailOut.eval_breakdown` now uses `EvalBreakdownOut`. JSONB may still store the field; Out strips it.
  - **Verified:** 3 new router tests in `tests/routers/test_generated_emails.py` — owner happy path (asserting `violation_detail` absent even when present on the persisted JSONB), nonexistent id → 404, wrong-owner → 404 (same `user_message` as missing). Full backend suite **123 passed**.
- **`GET /job-descriptions/{jd_id}` (prior session):** ownership-filtered read reusing `get_job_description_by_id`.
- **Frontend discovery flow UI (prior session):** three-frame state machine on `/`, TanStack `useMutation` for both POSTs, sessionStorage persistence/rehydration. Frontend: `npm run test:run` → **25 passed** (6 files) — unchanged this session.
- **Frontend auth foundation (prior session):** apiClient, AuthContext, Login/Signup, ProtectedRoute, TanStack Query root, Vitest wiring.
- **GENERATED_EMAILS persistence + generation endpoint** — `POST /generated-emails` + `generated_emails.py` orchestrator.
- **Postgres via Docker Compose** — `docker-compose.yml` at repo root, `postgres:18`.
- **Alembic migrations** — initial schema + `JOB_DESCRIPTIONS.user_id`; **9 tables**.
- **Auth (backend)** — signup/login/refresh/logout/me; bcrypt; opaque DB-backed refresh tokens.
- **Resume / JD upload + extract**, **MockProvider + HunterProvider** discovery, **Clearbit company resolution**, **LLM layer** (extraction, matching, email generation, eval with silent retry).

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite (covered at service layer + Hunter unit tests). Frontend now calls it; backend HTTP-layer gap unchanged.
- **`POST /auth/refresh`** — backend exists; frontend does **not** call it on 401 (scoped: redirect-to-login only).

### Not started

- **Frontend resume/JD upload → extract → generated-email UI** (next slice; accumulates on the same `/` home page).
- **Remaining real contact providers** — `ApolloProvider` / `AnymailProvider` deferred.
- **Refresh-token rotation / reuse-detection**, **cookie-based refresh transport**, **login rate-limiting** — deferred in `OPEN_QUESTIONS.md`.
- **`GENERATED_EMAILS.user_id` denormalization (Option B)** — deferred; Option A (join) shipped this session.

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
29. **`EvalGates.violation_detail` added after the original schema lock.** Free-form `str | None` (not a fixed violation-type enum), populated only when a Tier 1 gate fails, solely to feed `refine()`'s feedback argument. Not persisted independently (rides inside `eval_breakdown` JSONB). **Client exclusion now enforced** via `EvalGatesOut` / `EvalBreakdownOut` on `GeneratedEmailOut` (this session) — earlier "never shown" wording was aspirational until that Out split.
30. **`EmailDraft` is a non-persisted schema** (`subject` + `body`) for generation/refine LLM I/O. Separate from `GeneratedEmailOut` so ephemeral draft shapes aren't conflated with the persisted API response.
31. **`generate_email` / `evaluate_email` take explicit primitives** (`contact_name`, `contact_title`, `company_name`, `role_title` as needed) plus `MatchData` / `EmailDraft` — not ORM/DB objects, no DB session. Ownership/loading lives in `generated_emails.py`.
32. **`evaluate_with_retry` owns gate-retry orchestration inside `eval.py`**, not a separate module and not the router. `refine` stays the standalone reusable primitive for the product doc's v1.1+ multi-turn path. On gate failure with a missing `violation_detail`, a short fallback feedback string is used so `refine` always receives `str`.
33. **`contact_name=None` fallback handling is explicit in both prompts:** generation instructs a generic professional greeting and forbids fabricating a name; eval treats that generic greeting as a pass for `correct_contact_name_used` when `contact_name` is null.
34. **`eval_prompt` / `evaluate_email` / `evaluate_with_retry` gained `company_name` + `role_title` before commit.** Gap in the original task spec (generation already had them; eval didn't) — caught in review, not a Cursor deviation. Needed so `role_company_specificity` grades accuracy against trusted DB ground truth. `refine()` deliberately left unchanged (`email` + `feedback` only).
35. **`app/services/generated_emails.py` is a separate orchestrating service from `email_generation.py`.** `email_generation.py` stays a pure LLM call site (primitives in → `EmailDraft` out, no DB) per ARCHITECTURE.md §3's four-LLM-services table. Persistence, ownership checks, company consistency, score aggregation, and insert live in `generated_emails.py` — same "thick service, thin router" pattern as `contact_discovery.py`. Not a fifth LLM call site; §3's table is unchanged.
36. **Always-insert-never-overwrite on `GENERATED_EMAILS`.** Deliberate divergence from `extraction.py`'s overwrite-in-place: each regeneration produces a new row so future `OUTCOMES` FKs remain valid. Same `(contact_id, resume_id, job_description_id)` → multiple rows is expected.
37. **`eval_score` is the plain unweighted average of the five `EvalDimensions` ints**, always computed regardless of `gate_passed`. No zeroing/omitting on gate failure; gates are a separate boolean column.
38. **Company/contact consistency check** — server rejects with `ValidationError` when `contact.company_id != job_description.company_id`. Defense-in-depth; frontend filtering is a Phase 3 forward note (see `OPEN_QUESTIONS.md`).
39. **Frontend auth foundation — contract verification vs. task assumptions:**
    - **Signup returns tokens immediately** — confirmed against `auth.py`: `POST /auth/signup` → `TokenPairOut` (201). Matches the prompt assumption.
    - **Server-side logout exists** — `POST /auth/logout` with `{refresh_token}` → 204. `AuthContext.logout` calls it (then always clears localStorage). Not client-only.
    - **Refresh endpoint exists** — `POST /auth/refresh` with `{refresh_token}` → `TokenPairOut`. Intentionally unused on 401 this slice (redirect-to-login only).
    - **401 handler scopes to sent Authorization** — `/auth/login` also returns 401 for bad credentials (`Incorrect email or password`). Shared clear+redirect only runs when a Bearer token was actually attached, so login/signup forms can surface `user_message` without a full-page reload. Documented in `ARCHITECTURE.md` §8.
40. **Discovery-flow UI sessionStorage key shape:** single key `discoveryFlow` storing `{ company: { name, domain } | null, discoveryResult: ContactDiscoveryResponse | null }` — matches the prompt's specified shape (no deviation). Manual fallback collects both company name and domain (domain alone would leave FRAME 2 confirmation without a display name); name is prefilled from the failed/empty search query when available.
41. **`GET /job-descriptions/{jd_id}` (prior session):** no deviations from the prompt. Helper already enforced id+user_id; route is a one-liner reuse.
42. **`GET /generated-emails/{id}` (this session):** Option A (join via resume) shipped as specified — no silent upgrade to Option B. Pre-existing `violation_detail` client exposure was a real bug (docs claimed "never shown"; schema did not enforce it); fixed with Out-only gates shapes rather than leaving it. No other deviations from the prompt. `ARCHITECTURE.md` / `product_discovery_summary.md` untouched.

---

## What's next

1. **Frontend resume/JD upload → extract → generated email** on the same persistent `/` home page. Highest remaining risk before the app itself is demoable.
2. **Stretch, only if time remains:** Apollo/Anymail, outcome-logging polish, basic analytics view.

---

## Doc notes from this session

- **`DATA_MODEL.md` §2.7:** schema snippet updated for `EvalGatesOut` / `EvalBreakdownOut` and `GeneratedEmailOut.eval_breakdown: EvalBreakdownOut`; new decision notes for (1) API-boundary fix for `violation_detail`, (2) join-based GET ownership + write-time invariant.
- **`OPEN_QUESTIONS.md`:** new Explicitly deferred entry "GENERATED_EMAILS.user_id denormalization" (Option A shipped, Option B deferred with analytics/load-test trigger). Resolved `violation_detail` entry updated to note the Out-schema enforcement.
- **`ARCHITECTURE.md` / `product_discovery_summary.md`:** untouched — nothing in this slice contradicted what they already say.
- **`PROGRESS.md`:** overwritten for this slice.
