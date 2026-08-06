# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-05 — outcome logging Slice 1 (FRAME 6 "Mark as Sent" frontend); no backend changes.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Mark as Sent on FRAME 6 (this session):** Once a generated email result exists (live generate success or `sessionStorage` rehydration), FRAME 6 shows **Mark as Sent** beside Copy. `useMutation` → `POST /outcomes` with `{ generated_email_id, event_type: "sent" }` — explicit click, no auto-fire; surfaces `ApiError.user_message` with Retry on failure. Success → disabled "✓ Marked as sent" (frontend UX guard only; backend still allows multiple SENT rows). Flag `sentOutcomeLogged` added to the existing `discoveryFlow` sessionStorage object (not a sibling key); rehydration with the flag shows confirmed state with no network call. Client: `frontend/src/lib/outcomeApi.ts` + `outcomeTypes.ts`. **Frontend suite run:** `npm run test:run -- src/pages/HomePage.test.tsx` → **25/25 passed** (includes 3 new Mark as Sent cases: success+persist, error+Retry, rehydrate confirmed). No manual browser dogfood this session. No backend changes; `POST /outcomes` reused as-is.
- **OUTCOMES backend (prior):** migration `75ea1b948b2a` (`user_id` on outcomes); thin router + thick service; service tests previously green.
- **Inroad rebrand; FRAME 1–6; auth; Postgres; Alembic; Hunter/Mock discovery; LLM extract/match/generate/eval; closing strip.**

### Present, but not yet exercised by anything

- **`POST /contacts/discover` HTTP path** — mounted; no dedicated router TestClient suite.
- **`POST /auth/refresh`** — backend exists; frontend does not call it on 401.
- **GET-by-id refetch paths** — available; flow rehydrates from sessionStorage instead.
- **`GET /outcomes`** — mounted and service-tested; no frontend caller yet (Slice 1 does not poll or re-verify).
- **Other outcome event types from UI** — backend accepts them; FRAME 6 only logs `sent` for the current email (Slice 2).

### Not started

- **Analytics view (frontend)**, **Slice 2 outcome UI** (any event type against any past email), **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **public/live deployment**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**.

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
9. **sessionStorage key `discoveryFlow`:** `{ company, discoveryResult, resume, jobDescription, generatedEmail, sentOutcomeLogged }`.
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry` with defaults for JSONB backward compat. Deterministic post-eval signature append; generation/refine prompts forbid model closings.
11. **Model-closing strip (rounds 1–2):** `_strip_trailing_closing` between `evaluate_with_retry` and signature append. Round 2 = anchor-then-sweep.
12. **`OUTCOMES.user_id` denormalized** (migration `75ea1b948b2a`) — deliberate divergence from deferred `GENERATED_EMAILS.user_id`; see `DATA_MODEL.md` §2.8 / `OPEN_QUESTIONS.md`.

---

## What's next

1. **Outcome logging Slice 2** — generic UI to log any event type against any past generated email (see `OPEN_QUESTIONS.md` forward-note).
2. **Analytics view** against `GET /outcomes`.
3. **Manual dogfood** of Mark as Sent + generated emails in real outreach.
4. **Stretch — rate-limiting** before any public deploy.

---

## Test results (this session — actual suite output)

```
frontend: npm run test:run -- src/pages/HomePage.test.tsx — 25 passed
  (includes Mark as Sent: success+persist, error+Retry, rehydrate confirmed)
```

**Not run this session:** full frontend suite (`vitest run` without path filter), backend suite, live LLM/provider calls, manual browser walkthrough of Mark as Sent against a running API. Verification for this slice is the HomePage Vitest file only — no separate `GeneratedEmailStep` unit suite.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for outcome-logging Slice 1 (frontend).
- **`ARCHITECTURE.md`:** §8.2.2 extended for `sentOutcomeLogged`; §8.2.4 documents Mark as Sent + frontend-only duplicate-click guard.
- **`OPEN_QUESTIONS.md`:** forward-note under "Not yet discussed" for Slice 2 (any event type / any past email).
- **`DATA_MODEL.md` / `product_discovery_summary.md`:** untouched.
