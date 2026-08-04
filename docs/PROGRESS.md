# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-03 — resume `candidate_name` + `projects` extraction, matching evidence instruction, and post-eval deterministic signature append.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Resume projects + signature name (this session):**
  - **Root cause (dogfooding):** Generated emails never cited personal/academic/hackathon projects and signed off with no name — both were `ResumeExtraction` schema gaps (skills/experience/education only), not generation-prompt bugs.
  - **Schema:** `candidate_name: str | None = None`, `ProjectEntry`, `projects: list[ProjectEntry] = []` on `ResumeExtraction` — defaults so pre-existing `extracted_data` JSONB still deserializes (same pattern as `EvalGates.no_unprompted_gap_admission`).
  - **Prompts:** extraction rules for name + projects (with experience/project ambiguity guidance); matching explicitly treats `projects` as valid `resume_evidence` / strengths; generation + refine forbid model-authored sign-offs.
  - **Orchestration:** after `evaluate_with_retry`, append `"\n\nBest regards,\n{name}"` or `"\n\nBest regards,"` before persist — judge never sees the signature.
  - **FRAME 4:** renders `candidate_name` (correctness: wrong name → wrong signed email) and `projects`.
- **Third eval hard gate — no unprompted gap admission (prior session).**
- **Live mock-mode discovery fixtures (prior session).**
- **Frontend FRAME 1–6** — discovery → resume/JD extract → generate email, sessionStorage rehydration.
- **`GET /generated-emails/{id}`**, **`GET /job-descriptions/{jd_id}`**, auth, Postgres, Alembic (9 tables), Hunter/Mock discovery, LLM extraction/matching/generation/eval.

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite.
- **`POST /auth/refresh`** — backend exists; frontend does not call it on 401.
- **GET-by-id refetch paths** — available; flow rehydrates from sessionStorage instead.

### Not started

- **Outcome logging**, **analytics view**, **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**.

---

## Deviations from `ARCHITECTURE.md` / `DATA_MODEL.md`

*Carry-forward notes from prior sessions that still apply; full historical list trimmed where superseded by docs.*

1. **Enum location:** `app/core/enums.py`. **`DeclarativeBase`** in `db/base.py`. Alembic model registration in `alembic/env.py`.
2. **`extracted_data` is JSONB** (omitted from §3.5 list). **9 tables.** bcrypt + SHA-256 refresh; access 30m / refresh 30d; PyJWT.
3. **`AppException` client key is `user_message`.** Resume HTTP create is multipart `file`, not JSON `ResumeCreate`.
4. **`JOB_DESCRIPTIONS.user_id`** via migration `97807b9a3c89`. Discovery path `POST /contacts/discover`.
5. **LLM defaults:** `claude-haiku-4-5`, `llm_max_retries=1`, `max_tokens=4096`, `LLMExtractionError` → 502.
6. **`MatchData` lives in `app/schemas/generated_email.py`.** No dedicated match HTTP endpoint.
7. **`EvalGates.violation_detail`** + **`no_unprompted_gap_admission`** post-lock revisions; Out shapes strip `violation_detail`.
8. **`generated_emails.py`** is the DB orchestrator; `email_generation.py` stays pure LLM. Always-insert-never-overwrite. `eval_score` = unweighted mean of five dimensions.
9. **sessionStorage key `discoveryFlow`:** `{ company, discoveryResult, resume, jobDescription, generatedEmail }`.
10. **This session — `ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry` with defaults for JSONB backward compat. Deterministic post-eval signature append in `generated_emails.py`; generation/refine prompts forbid model closings. `candidate_name` from resume text (not USERS profile) — see `OPEN_QUESTIONS.md`.

---

## What's next

1. **Manual dogfood** of project citation in match/email and signature name accuracy after re-extracting a real resume.
2. **Revisit `candidate_name` source** if mis-extraction shows up often (OPEN_QUESTIONS trigger).
3. **Stretch — outcome logging / analytics**; deferred providers/auth hardening only if usage demands.

---

## Test results (this session — actual suite output)

**Backend** (`pytest -ra` from `backend/`):

```
================= 12 failed, 124 passed, 75 warnings in 33.56s =================
```

Failed (investigated — not assumed “unrelated”):

| File | Tests | Cause |
|---|---|---|
| `test_contact_discovery.py` | 6 | Pre-existing: discover hits cached `Contact` for `acme.com` (scripted Alex Recruiter) so `tier_used` is `None` / confidence assertions miss. Unchanged by this branch. |
| `test_generated_emails.py` | 6 error-path tests (`wrong_owner_*`, `missing_contact`, `*_missing_extracted_data`, `company_mismatch`) | Pre-existing isolation leak: `assert GeneratedEmail.count() == 0` sees **2 leftover rows** already committed in Postgres. `pytest.raises(...)` still passes (errors raise correctly). Happy path + all 3 new signature tests pass. Not caused by signature append. |

New coverage added this session (all passing when run with related files): extraction present/absent `candidate_name`/`projects`, matching project-evidence prompt + pipeline, signature named / None / once-after-refine; email-generation prompt asserts sign-off forbid.

**Frontend** (`npm run test:run` from `frontend/`):

```
 Test Files  8 passed (8)
      Tests  45 passed (45)
```

Addendum: `ResumeStep.test.tsx` covers `candidate_name` present/null, projects present (full fields + sparse empty conditionals), and empty-projects fallback. HomePage full-extract fixture assertions extended for project description / technologies / bullets; FRAME 4 rehydrate asserts `No projects extracted.`

---

## Doc notes from this session

- **`DATA_MODEL.md` §2.2:** `candidate_name` + `ProjectEntry`/`projects` Decision (revision) + backward-compat defaults.
- **`ARCHITECTURE.md` §3:** post-eval signature append; generation/refine forbid model closings. §8.2.3: FRAME 4 shows name + projects.
- **`OPEN_QUESTIONS.md`:** resume-text vs USERS-profile decision for `candidate_name` + revisit trigger.
- **`product_discovery_summary.md`:** not edited — extraction completeness is a DATA_MODEL decision, not an MVP-scope change. (Existing `candidate_name` mentions there refer to `RAW_PROVIDER_RESULTS`, unrelated.)
- **`PROGRESS.md`:** overwritten for this slice.
