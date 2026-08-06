# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-05 — OUTCOMES backend slice (append-only event log + denormalized `user_id`); no frontend work.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **OUTCOMES backend (this session):** Additive migration `75ea1b948b2a` adds `user_id` (FK → users, NOT NULL, indexed) to the existing `outcomes` table. ORM updated; `OutcomeCreate`/`OutcomeOut` schemas added (`app/schemas/outcome.py` — were doc-only before; `OutcomeOut` deliberately omits `user_id`). Service `app/services/outcomes.py`: `create_outcome` reuses `get_generated_email_by_id` for ownership, sets `user_id` from `current_user.id`; `list_outcomes` filters on `Outcome.user_id` directly with optional `generated_email_id`. Thin router `POST/GET /outcomes` wired in `main.py`. **3/3 service-level tests passed** (`tests/services/test_outcomes.py`: wrong-owner → NotFoundError; append-only multi-row; list scoped + filterable). No HTTP TestClient suite (thin-router pattern). No analytics view / frontend outcome UI yet.
- **Inroad rebrand (prior):** naming + logo/favicon + header lockup; no schema/pipeline behavior changes beyond static assets.
- **Anchor-then-sweep closing strip; Frontend FRAME 1–6; auth; Postgres; Alembic; Hunter/Mock discovery; LLM extract/match/generate/eval.**

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite.
- **`POST /auth/refresh`** — backend exists; frontend does not call it on 401.
- **GET-by-id refetch paths** — available; flow rehydrates from sessionStorage instead.
- **`POST /outcomes` / `GET /outcomes` HTTP paths** — mounted and service-tested; no router TestClient suite and no frontend caller yet.

### Not started

- **Analytics view (frontend)**, **outcome logging UI**, **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **public/live deployment**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**.

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
11. **Model-closing strip (rounds 1–2):** `_strip_trailing_closing` between `evaluate_with_retry` and signature append. Round 2 = anchor-then-sweep.
12. **`OUTCOMES.user_id` denormalized** (migration `75ea1b948b2a`) — deliberate divergence from deferred `GENERATED_EMAILS.user_id`; see `DATA_MODEL.md` §2.8 / `OPEN_QUESTIONS.md`. Schemas were previously documented but not implemented as a Python module — now at `app/schemas/outcome.py`.

---

## What's next

1. **Frontend outcome logging UI** (and later analytics view) against `POST/GET /outcomes`.
2. **Manual dogfood** of generated emails / closing strip in real outreach.
3. **Revisit `candidate_name` source** if mis-extraction shows up often (OPEN_QUESTIONS trigger).
4. **Stretch — rate-limiting** before any public deploy; deferred providers/auth hardening only if usage demands.

---

## Test results (this session — actual suite output)

```
tests/services/test_outcomes.py — 3 passed
  test_create_outcome_wrong_owner_raises_not_found
  test_create_multiple_outcomes_same_email_succeeds
  test_list_outcomes_scoped_and_filterable
```

**Not run this session:** full backend suite, frontend tests, router TestClient for `/outcomes`, live LLM/provider calls. Migration `75ea1b948b2a` applied locally (`alembic upgrade head` → `75ea1b948b2a`).

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for this OUTCOMES backend session.
- **`DATA_MODEL.md`:** §2.8 revision note for `user_id`; §3.1 additive migrations list; §3.6 FK index list; §3.8 dependency diagram; brand note clarified.
- **`OPEN_QUESTIONS.md`:** cross-ref under `GENERATED_EMAILS.user_id` explaining deliberate opposite call for OUTCOMES.
- **`ARCHITECTURE.md`:** new §9 Outcomes router/service + ownership-reuse pattern.
- **`product_discovery_summary.md`:** untouched — MVP #6/#7 still match; no contradiction found.
