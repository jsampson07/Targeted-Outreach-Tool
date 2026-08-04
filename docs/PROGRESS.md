# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-03 — deterministic strip of model-authored trailing email closings before programmatic signature append.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Strip model-authored trailing closing (this session):**
  - **Root cause (dogfooding):** Generation/refine prompts forbid sign-offs, but `claude-haiku-4-5` does not reliably obey that negative instruction. A model-written `"Best,"` stacked with the programmatic `"Best regards,\n{name}"` — a broken double closing in copy-paste output.
  - **Fix:** `_strip_trailing_closing` in `generated_emails.py` runs after `evaluate_with_retry` returns and before the existing signature append. Judge still sees raw model output.
  - **Detection (conservative):** last 1–3 non-blank lines only; exact standalone valediction match after trimming one trailing comma/period; optional following `candidate_name` line also stripped. Mid-sentence "thanks"/"regards" left alone.
  - **Rejected alternative:** fourth eval hard gate — probabilistic retry via the same model; strip is a guarantee.
  - **Cleanup:** removed unreachable forward-`after` lookahead from the closing-line branch (`window[0]` is always the last non-blank line, so closing+name is handled by the name-first branch). Full `test_generated_emails.py` re-run; no assertion changes.
- **Resume projects + signature name (prior session):** `candidate_name` / `projects` on `ResumeExtraction`; matching treats projects as evidence; post-eval signature append; FRAME 4 surfaces name + projects.
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
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry` with defaults for JSONB backward compat. Deterministic post-eval signature append; generation/refine prompts forbid model closings. `candidate_name` from resume text (not USERS profile) — see `OPEN_QUESTIONS.md`.
11. **This session — model-closing strip:** `_strip_trailing_closing` between `evaluate_with_retry` and signature append. Not a schema change; fourth eval gate explicitly rejected (see `ARCHITECTURE.md` §3 / `OPEN_QUESTIONS.md`).

---

## What's next

1. **Manual dogfood** of generated emails after re-extract — confirm no double closings and project citation / signature name still look right.
2. **Revisit `candidate_name` source** if mis-extraction shows up often (OPEN_QUESTIONS trigger).
3. **Stretch — outcome logging / analytics**; deferred providers/auth hardening only if usage demands.

---

## Test results (this session — actual suite output)

**Backend** (`pytest tests/services/test_generated_emails.py -ra` from `backend/`):

Re-run after dead-branch removal:

```
=================== 6 failed, 18 passed, 1 warning in 4.89s ====================
```

Failed (pre-existing isolation leak — unchanged by this branch):

| File | Tests | Cause |
|---|---|---|
| `test_generated_emails.py` | 6 error-path tests (`wrong_owner_*`, `missing_contact`, `*_missing_extracted_data`, `company_mismatch`) | `assert GeneratedEmail.count() == 0` sees leftover committed rows. `pytest.raises(...)` still passes. |

All strip/signature assertions unchanged and still passing, including closing+name cases: `test_strip_trailing_closing_phrase_plus_candidate_name`, `test_signature_strips_model_closing_before_append`, `test_signature_appended_once_after_refine_pass`.

**Frontend:** not exercised this session (backend-only strip fix).

---

## Doc notes from this session

- **`ARCHITECTURE.md` §3:** added follow-up Decision (strip model-authored closing before signature append) — root cause, rejected fourth eval gate, pipeline position relative to `evaluate_with_retry`. Dead-branch cleanup: no edit — wording describes behavior ("a following `candidate_name` line, when present"), not the removed forward-lookahead mechanic.
- **`OPEN_QUESTIONS.md`:** new Resolved entry for model-authored closing stacked with programmatic signature. Dead-branch cleanup: no edit — entry is implementation-detail-light.
- **`PROGRESS.md`:** overwritten for this slice; amended for dead-branch removal + re-run results.
- **`product_discovery_summary.md`:** not edited — implementation-level bug fix / internal cleanup, not an MVP-scope or roadmap change.
- **`DATA_MODEL.md`:** not edited — no schema/column change.
