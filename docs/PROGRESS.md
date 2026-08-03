# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-03 — frontend generate-email trigger + result display (FRAME 6) on `/`. Frontend: `npm run test:run` → **39 passed** (7 files). Backend suite unchanged this session (no backend edits; prior **123 passed**).*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Frontend generate-email UI / FRAME 6 (this session):**
  - Extends the `/` home-page frame flow after JD extract: explicit **Generate Email** `useMutation` → `POST /generated-emails` with `{ contact_id, resume_id, job_description_id }` → render `GeneratedEmailOut`.
  - Result UI: subject/body, paste-ready copy-to-clipboard (`Subject: …\n\n<body>` — no mailto/send), `eval_score` + flagged indicator when `gate_passed` is false, dimensions + two Out-only gate booleans, `match_data.overall_match_summary` inline + remaining match fields in collapsed `<details>` (mirrors discovery `confidence_breakdown`).
  - Single-shot: after success or sessionStorage rehydrate, Generate button is hidden; failed attempts before success may Retry.
  - **sessionStorage:** extended existing `discoveryFlow` key with `generatedEmail: GeneratedEmailOut | null`.
  - `useResumeForGeneration` public interface unchanged (`resumeId` consumed as-is).
  - **Verified:** HomePage tests for mutation success + persistence, 422 `user_message` + Retry, FRAME 6 rehydrate with flagged gates, clipboard copy; suite **39 passed** (7 files).
- **Frontend resume + JD upload/extract UI (prior session):** FRAME 4–5, `useResumeForGeneration`, sessionStorage `resume` / `jobDescription`.
- **`GET /generated-emails/{generated_email_id}` (prior session):** join-based ownership + `EvalBreakdownOut` stripping `violation_detail`.
- **`GET /job-descriptions/{jd_id}` (prior session):** ownership-filtered read.
- **Frontend discovery flow UI (prior session):** FRAME 1–3 state machine, `useMutation`, sessionStorage rehydration.
- **Frontend auth foundation (prior session):** apiClient, AuthContext, Login/Signup, ProtectedRoute, TanStack Query root, Vitest wiring.
- **GENERATED_EMAILS persistence + generation endpoint** — `POST /generated-emails` + `generated_emails.py` orchestrator.
- **Postgres via Docker Compose** — `docker-compose.yml` at repo root, `postgres:18`.
- **Alembic migrations** — initial schema + `JOB_DESCRIPTIONS.user_id`; **9 tables**.
- **Auth (backend)** — signup/login/refresh/logout/me; bcrypt; opaque DB-backed refresh tokens.
- **Resume / JD upload + extract**, **MockProvider + HunterProvider** discovery, **Clearbit company resolution**, **LLM layer** (extraction, matching, email generation, eval with silent retry).

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite (covered at service layer + Hunter unit tests). Frontend now calls it; backend HTTP-layer gap unchanged.
- **`POST /auth/refresh`** — backend exists; frontend does **not** call it on 401 (scoped: redirect-to-login only).
- **`GET /job-descriptions/{jd_id}` / `GET /resumes/{id}` / `GET /generated-emails/{id}`** — available for refetch-by-id; this slice rehydrates paid results from sessionStorage instead.

### Not started

- **Outcome logging** (OUTCOMES table — sent / no-response / replied / interview) — stretch.
- **Analytics view** — stretch / Phase 4.
- **Remaining real contact providers** — `ApolloProvider` / `AnymailProvider` deferred.
- **Refresh-token rotation / reuse-detection**, **cookie-based refresh transport**, **login rate-limiting** — deferred in `OPEN_QUESTIONS.md`.
- **`GENERATED_EMAILS.user_id` denormalization (Option B)** — deferred; Option A (join) shipped previously.
- **Resume picker / reuse (Option 3)** — deferred; Option 2 shipped with hook isolation boundary.
- **Regenerate-email control** — deferred; v1 single-shot only (see `OPEN_QUESTIONS.md`).

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
10. **Resume upload parsing / limits:** pypdf / python-docx; 2MB cap; min 50 chars extracted text. **HTTP create is multipart `file`**, not JSON `ResumeCreate`.
11. **`JOB_DESCRIPTIONS.user_id`** via migration `97807b9a3c89` — live model/API have it.
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
29. **`EvalGates.violation_detail` added after the original schema lock.** Free-form `str | None` (not a fixed violation-type enum), populated only when a Tier 1 gate fails, solely to feed `refine()`'s feedback argument. Not persisted independently (rides inside `eval_breakdown` JSONB). **Client exclusion now enforced** via `EvalGatesOut` / `EvalBreakdownOut` on `GeneratedEmailOut`.
30. **`EmailDraft` is a non-persisted schema** (`subject` + `body`) for generation/refine LLM I/O. Separate from `GeneratedEmailOut` so ephemeral draft shapes aren't conflated with the persisted API response.
31. **`generate_email` / `evaluate_email` take explicit primitives** (`contact_name`, `contact_title`, `company_name`, `role_title` as needed) plus `MatchData` / `EmailDraft` — not ORM/DB objects, no DB session. Ownership/loading lives in `generated_emails.py`.
32. **`evaluate_with_retry` owns gate-retry orchestration inside `eval.py`**, not a separate module and not the router. `refine` stays the standalone reusable primitive for the product doc's v1.1+ multi-turn path. On gate failure with a missing `violation_detail`, a short fallback feedback string is used so `refine` always receives `str`.
33. **`contact_name=None` fallback handling is explicit in both prompts:** generation instructs a generic professional greeting and forbids fabricating a name; eval treats that generic greeting as a pass for `correct_contact_name_used` when `contact_name` is null.
34. **`eval_prompt` / `evaluate_email` / `evaluate_with_retry` gained `company_name` + `role_title` before commit.** Gap in the original task spec (generation already had them; eval didn't) — caught in review, not a Cursor deviation. Needed so `role_company_specificity` grades accuracy against trusted DB ground truth. `refine()` deliberately left unchanged (`email` + `feedback` only).
35. **`app/services/generated_emails.py` is a separate orchestrating service from `email_generation.py`.** `email_generation.py` stays a pure LLM call site (primitives in → `EmailDraft` out, no DB) per ARCHITECTURE.md §3's four-LLM-services table. Persistence, ownership checks, company consistency, score aggregation, and insert live in `generated_emails.py` — same "thick service, thin router" pattern as `contact_discovery.py`. Not a fifth LLM call site; §3's table is unchanged.
36. **Always-insert-never-overwrite on `GENERATED_EMAILS`.** Deliberate divergence from `extraction.py`'s overwrite-in-place: each regeneration produces a new row so future `OUTCOMES` FKs remain valid. Same `(contact_id, resume_id, job_description_id)` → multiple rows is expected.
37. **`eval_score` is the plain unweighted average of the five `EvalDimensions` ints**, always computed regardless of `gate_passed`. No zeroing/omitting on gate failure; gates are a separate boolean column.
38. **Company/contact consistency check** — server rejects with `ValidationError` when `contact.company_id != job_description.company_id`. Defense-in-depth; happy-path UI now feeds IDs from the same discovery→JD pipeline so the 422 should not appear in normal use, but the client still surfaces `user_message` if it does.
39. **Frontend auth foundation — contract verification vs. task assumptions:**
    - **Signup returns tokens immediately** — confirmed against `auth.py`: `POST /auth/signup` → `TokenPairOut` (201). Matches the prompt assumption.
    - **Server-side logout exists** — `POST /auth/logout` with `{refresh_token}` → 204. `AuthContext.logout` calls it (then always clears localStorage). Not client-only.
    - **Refresh endpoint exists** — `POST /auth/refresh` with `{refresh_token}` → `TokenPairOut`. Intentionally unused on 401 this slice (redirect-to-login only).
    - **401 handler scopes to sent Authorization** — `/auth/login` also returns 401 for bad credentials (`Incorrect email or password`). Shared clear+redirect only runs when a Bearer token was actually attached, so login/signup forms can surface `user_message` without a full-page reload. Documented in `ARCHITECTURE.md` §8.
40. **Discovery-flow UI sessionStorage key shape:** single key `discoveryFlow` — originally `{ company, discoveryResult }`; extended to `{ company, discoveryResult, resume, jobDescription }`; **this session extended** to `{ company, discoveryResult, resume, jobDescription, generatedEmail }` (same key, not a sibling).
41. **`GET /job-descriptions/{jd_id}` (prior session):** no deviations from the prompt. Helper already enforced id+user_id; route is a one-liner reuse.
42. **`GET /generated-emails/{id}` (prior session):** Option A (join via resume) shipped as specified — Out-only gates shapes for `violation_detail`.
43. **Resume/JD frontend slice (prior session) — Step 0 contract vs docs:**
    - **Resume HTTP create is multipart `file`**, not JSON `ResumeCreate{raw_text}`.
    - **JD create is JSON** `{raw_text, company_id, role_title}` as documented; Out includes `user_id`.
    - **Paths:** `POST /resumes`, `POST /resumes/{id}/extract`, `POST /job-descriptions`, `POST /job-descriptions/{jd_id}/extract`, `GET /job-descriptions/{jd_id}` — match live `main.py` prefixes.
    - **`company_id` is not on Frame 1's locked company** — only on found `ContactOut`. Contact-null discovery cannot continue to JD without a backend change; UI gates Continue accordingly.
44. **Generate-email frontend slice (this session) — Step 0 contract vs docs:**
    - **No schema/contract gap vs `DATA_MODEL.md` §2.7.** Live `GenerateEmailRequest` / `GeneratedEmailOut` / `EvalGatesOut` / `MatchData` match the documented shapes. `gate_passed` is top-level. `EvalGatesOut` omits `violation_detail` on the POST response (same Out model as GET-by-id). `DATA_MODEL.md` left untouched.
    - **Path:** `POST /generated-emails` confirmed via `main.py` prefix + router `POST ""`.
    - **422 mismatch `user_message`:** `"Contact and job description must belong to the same company. Contact is tied to company_id=…; job description is tied to company_id=…."` — frontend surfaces via `ApiError.user_message`.
    - **Backend files live under `backend/app/…`** (monorepo layout); prompt paths `app/routers/…` resolve there.

---

## What's next

1. **Stretch — outcome logging** (OUTCOMES: sent / no-response / replied / interview) once the demo loop has been exercised in a real job search.
2. **Stretch — basic analytics view** (Phase 4).
3. **Deferred providers / auth hardening** as listed under Not started / `OPEN_QUESTIONS.md` — only if real usage demands them.

---

## Doc notes from this session

- **`ARCHITECTURE.md`:** §8.1/§8.2.1/§8.2.2 updated for generate-email; new §8.2.4 documenting FRAME 6 (trigger, verified contract, copy-to-clipboard, gate_passed flagged UI, match_data collapsed-details mirroring confidence_breakdown, single-shot, sessionStorage `generatedEmail`).
- **`DATA_MODEL.md`:** untouched — live contract matched §2.7 (no gap to fill).
- **`OPEN_QUESTIONS.md`:** new Explicitly deferred entry for single-shot vs regenerate (prompt-quality-first if revisit).
- **`product_discovery_summary.md`:** untouched — MVP scope unchanged (grounded generation + rubric check already locked; this slice only landed the UI).
- **`PROGRESS.md`:** overwritten for this slice.
