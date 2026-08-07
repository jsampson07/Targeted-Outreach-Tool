# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-07 — OUTCOMES SENT gate + retract cascade.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **OUTCOMES SENT uniqueness + create-time gate + retract cascade (this session):**
  - Additive migration `e8a3c71f2049`: partial unique index `uq_outcomes_generated_email_id_nonvoided_sent` on `outcomes (generated_email_id) WHERE voided = false AND event_type = 'sent'`. Declared on the ORM via `__table_args__`. Applied locally via `alembic upgrade head`.
  - `create_outcome`: app-level gate via `list_outcomes` — reject second non-voided SENT; reject non-SENT without a prior non-voided SENT. `IntegrityError` on the unique index translated to the same already-sent `ValidationError` (race backstop).
  - `retract_outcome`: voiding a non-voided SENT also voids every other non-voided outcome for that `generated_email_id` in the same transaction (siblings via `list_outcomes`). Non-SENT retract unchanged (no cascade). Fresh SENT after retract succeeds.
  - `/history` log form: disable Sent when a non-voided Sent exists; disable other event types until Sent exists (in-memory group only — no new fetch).
  - `/history` retract: inline cascade confirm copy when retracting Sent with other non-voided outcomes; existing `OUTCOMES_QUERY_KEY` invalidation refetches all newly voided rows.
  - FRAME 6 Mark as Sent: left `sentOutcomeLogged` sessionStorage guard in place; backend rejection already surfaces `ApiError.user_message` (confirmed — no code change required).
- **Backend tests run this session:**
  ```
  pytest tests/services/test_outcomes.py
  → 11 passed
  ```
- **Frontend tests run this session:**
  ```
  npm run test:run
  → Test Files  10 passed (10)
  → Tests  60 passed (60)
  ```
  New coverage: log-form option enablement; Sent retract cascade confirm copy. Existing log test updated to log Sent first (only enabled option when unlogged).
  `tsc -b` clean.
- **Prior slices unchanged:** history expand accordion, `/analytics`, Slice 2a/2b otherwise, FRAME 6 Mark as Sent UX.

### Present, but not yet exercised by anything

- **Manual browser dogfood** of SENT gate / cascade confirm on `/history`, and of Mark as Sent after the backend constraint.
- **Manual browser dogfood of `/history` expand animation** — still pending from prior session.
- **Manual browser dogfood of `/analytics`** — still pending from prior session.
- **Router-level HTTP TestClient suites** for analytics / Slice 2a list/retract — still service-level / pure-function only.

### Not started

- **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **public/live deployment**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**, analytics cross-tab / date-range (deferred — see `OPEN_QUESTIONS.md`).

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
8. **`generated_emails.py`** is the DB orchestrator; always-insert-never-overwrite. `eval_score` = unweighted mean of five dimensions. Now also owns `list_generated_emails_for_analytics`.
9. **sessionStorage key `discoveryFlow`:** home flow only; `/history` and `/analytics` deliberately have none.
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry`. Deterministic post-eval signature append + `_strip_trailing_closing`.
11. **`OUTCOMES.user_id` denormalized** (migration `75ea1b948b2a`); **`voided`** added (migration `c4f8e2a91b07`); **one non-voided SENT** partial unique index (migration `e8a3c71f2049`) + create-time gate + SENT retract cascade — see `DATA_MODEL.md` §2.8 / `OPEN_QUESTIONS.md`.

**Doc/code check this session:** Docs updated to match the new gate/cascade. Prior §8.2.4 / §10.3 wording that allowed multiple SENT or left replies non-voided after SENT retract was rewritten. `product_discovery_summary.md` deliberately left as-is (implementation-level integrity decision; no MVP-scope change).

---

## What's next

1. **Manual browser dogfood** of SENT gate / cascade confirm on `/history`, Mark as Sent, expand animation, `/analytics`.
2. **Stretch — rate-limiting** before any public deploy.

---

## Test results (this session — actual suite output)

```
backend: pytest tests/services/test_outcomes.py
→ 11 passed

frontend: npm run test:run
→ Test Files  10 passed (10)
→ Tests  60 passed (60)

frontend: npx tsc -b
→ exit 0 (clean)

alembic upgrade head
→ Running upgrade c4f8e2a91b07 -> e8a3c71f2049
```

**Not run this session:** full backend suite beyond outcomes, live LLM/provider calls, manual browser walkthrough.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for SENT gate + retract cascade.
- **`DATA_MODEL.md`:** §2.8 decision note + §3.1 additive migration `e8a3c71f2049`.
- **`ARCHITECTURE.md`:** §8.2.4 Mark as Sent wording; §8.6 log-form gate + cascade confirm; §9 create gate + cascade; §10.3 retract interaction rewritten for cascade.
- **`OPEN_QUESTIONS.md`:** new Resolved entry; soft-delete "Future interaction — uniqueness on SENT" marked resolved with cross-ref.
- **`product_discovery_summary.md`:** left as-is — no MVP scope / value-proposition change.
