# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-04 — public README + light external-reader header pass on engineering docs; no code or schema changes.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Public root README (this session — docs only):** `/README.md` for recruiters/engineers; claims spot-checked against routers/services (auth, company search, contact discovery, resumes, JDs, generated emails) and frontend FRAME 1–6. Demo GIF is a placeholder (`docs/demo.gif` not yet added). No live deploy link — deferred on purpose.
- **Anchor-then-sweep closing strip (prior — dogfood round 2):** `_strip_trailing_closing` finds earliest `_is_closing_line` in last ≤3 non-blank window and sweeps from that anchor; bare-`candidate_name` fallback. Wiring unchanged (after `evaluate_with_retry`, before signature append).
- **Strip model-authored trailing closing (dogfood round 1);** resume projects + signature name; third eval hard gate; live mock discovery fixtures.
- **Frontend FRAME 1–6**; **`GET /generated-emails/{id}`**, **`GET /job-descriptions/{jd_id}`**, auth, Postgres, Alembic (9 tables), Hunter/Mock discovery, LLM extraction/matching/generation/eval.

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite.
- **`POST /auth/refresh`** — backend exists; frontend does not call it on 401.
- **GET-by-id refetch paths** — available; flow rehydrates from sessionStorage instead.
- **`OUTCOMES` model / schemas** — table exists; no outcomes router or UI yet.

### Not started

- **Outcome logging**, **analytics view**, **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **public/live deployment**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**.

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
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry` with defaults for JSONB backward compat. Deterministic post-eval signature append; generation/refine prompts forbid model closings.
11. **Model-closing strip (rounds 1–2):** `_strip_trailing_closing` between `evaluate_with_retry` and signature append. Round 2 = anchor-then-sweep. Not a schema change; fourth eval gate and phrase-list expansion both explicitly rejected (see `ARCHITECTURE.md` §3 / `OPEN_QUESTIONS.md`).

---

## What's next

1. **Manual dogfood** of generated emails after the strip fix — confirm stacked closings / trailing-sentence-after-Thanks cases are gone.
2. **Add `docs/demo.gif`** so the README Demo section renders.
3. **Revisit `candidate_name` source** if mis-extraction shows up often (OPEN_QUESTIONS trigger).
4. **Stretch — outcome logging / analytics**; rate-limiting before any public deploy; deferred providers/auth hardening only if usage demands.

---

## Test results (this session — actual suite output)

**No test suite run this session** — documentation-only changes (README + engineering-doc headers / deferral notes). Prior session strip-suite status unchanged: backend strip/signature tests passing with known pre-existing isolation leak on 6 error-path count assertions in `test_generated_emails.py`.

---

## Doc notes from this session

- **`README.md` (new):** Public-facing root README — pitch, problem, GIF placeholder, technical substance teaser, stack, Mermaid pipeline, local setup (mock-first discovery), honest status/roadmap, links to engineering docs. Claims verified against `app/routers/` + `app/services/` + frontend FRAME components; no invented metrics or live demo URL.
- **`OPEN_QUESTIONS.md`:** external-reader header added; existing "Login rate-limiting / brute-force protection" entry amended (not duplicated) — public README added, live deploy deliberately deferred until this gap closes (trigger actively evaluated).
- **`product_discovery_summary.md`:** external-reader header added; one new Deferred Features row — "Public / live deployment" (rate-limiting / LLM-cost exposure; points to `OPEN_QUESTIONS.md`).
- **`PROGRESS.md`:** overwritten for this docs session.
- **`ARCHITECTURE.md`:** external-reader header only — no content/decision changes (setup steps live in root README + `backend/.env.example`; nothing new to lock here).
- **`DATA_MODEL.md`:** external-reader header only — no schema/decision changes.
