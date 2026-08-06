# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-06 — outcome logging Slice 2a (backend: generated-email list + outcome retract); no frontend work.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Slice 2a backend (this session):**
  - `GET /generated-emails` → `list[GeneratedEmailListOut]` — ownership via Resume join (same as GET-by-id); joins Contact/Company for display fields; no outcome-status join; no pagination.
  - `POST /outcomes/{outcome_id}/retract` — one-way soft-delete (`voided=true`); ownership via denormalized `Outcome.user_id`; idempotent if already voided.
  - Migration `c4f8e2a91b07` — add `voided` to `outcomes` (`NOT NULL`, default `false`; no standalone index). Applied via `alembic upgrade head`.
  - `list_outcomes` filters `voided=false`.
  - **Correction within Slice 2a:** `OutcomeOut` includes `voided: bool` so `POST …/retract` can confirm the resulting state (earlier omit-voided note was wrong for the retract response; list still excludes voided rows, so the field reads `false` there). No behavior change beyond schema exposure.
  - Discipline rule written into `app/services/outcomes.py` module docstring: all OUTCOMES reads must go through that service.
- **Backend tests run this session (all passed):**
  ```
  pytest tests/services/test_outcomes.py \
         tests/services/test_generated_emails.py::test_list_generated_emails_ownership_scoped -v
  → 7 passed
  ```
  Coverage: prior create/list cases still green; new retract wrong-owner → NotFoundError; retract voids + excludes from list (create `voided=False` / retract `voided=True` via `OutcomeOut.model_validate`); retract already-voided is idempotent no-op; list_generated_emails ownership-scoped across two users.
- **OUTCOMES create/list + Mark as Sent FRAME 6 (prior):** unchanged; Slice 1 frontend still only logs `sent` for the current email.

### Present, but not yet exercised by anything

- **`GET /generated-emails` and `POST /outcomes/{id}/retract` HTTP paths** — mounted; verified at service level only (no dedicated router TestClient suite this session).
- **`GET /outcomes`** — mounted and service-tested; no frontend caller yet.
- **Other outcome event types from UI** — backend accepts them; FRAME 6 only logs `sent` (Slice 2b).

### Not started

- **Slice 2b frontend** (picker view, log-any-event UI, retract in UI), **Analytics view**, **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **public/live deployment**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**.

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
8. **`generated_emails.py`** is the DB orchestrator; always-insert-never-overwrite. `eval_score` = unweighted mean of five dimensions.
9. **sessionStorage key `discoveryFlow`:** `{ company, discoveryResult, resume, jobDescription, generatedEmail, sentOutcomeLogged }`.
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry`. Deterministic post-eval signature append + `_strip_trailing_closing`.
11. **`OUTCOMES.user_id` denormalized** (migration `75ea1b948b2a`); **`voided`** added (migration `c4f8e2a91b07`) — narrow retract exception to append-only; see `DATA_MODEL.md` §2.8 / `OPEN_QUESTIONS.md`.

---

## What's next

1. **Outcome logging Slice 2b** — frontend picker + log any event type + retract UI (see `OPEN_QUESTIONS.md` forward-note).
2. **Analytics view** against `GET /outcomes` (must use `services/outcomes.py`).
3. **Manual dogfood** of Mark as Sent + generated emails in real outreach.
4. **Stretch — rate-limiting** before any public deploy.

---

## Test results (this session — actual suite output)

```
backend: pytest tests/services/test_outcomes.py -v
→ 6 passed (includes OutcomeOut.voided create=False / retract=True assertions)
```

**Earlier this session (Slice 2a core):**
```
backend: pytest tests/services/test_outcomes.py \
                tests/services/test_generated_emails.py::test_list_generated_emails_ownership_scoped -v
→ 7 passed
alembic upgrade head → 75ea1b948b2a -> c4f8e2a91b07 (add voided to outcomes)
```

**Not run this session:** full backend suite, frontend suite, live LLM/provider calls, router-level HTTP tests for the new endpoints, manual browser walkthrough.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for Slice 2a backend; noted `OutcomeOut.voided` correction in same slice scope.
- **`DATA_MODEL.md`:** §2.7 `GeneratedEmailListOut`; §2.8 retract exception to append-only; §3.1 migration `c4f8e2a91b07`; corrected §2.8 to include `voided` on `OutcomeOut` (review gap).
- **`ARCHITECTURE.md`:** §9 endpoints + ownership patterns + all-reads-through-service discipline; Schemas line updated (`voided` on `OutcomeOut`, still omits `user_id`).
- **`OPEN_QUESTIONS.md`:** soft-delete vs hard-delete resolved; OUTCOMES row-growth deliberately not designed for; Slice 2 forward-note split into 2a done / 2b open.
