# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-06 — outcome logging Slice 2b (frontend `/history` page).*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Slice 2b frontend (this session):**
  - Protected route `/history` (`HistoryPage`) + Search/History nav on `AppHeader` (previously brand + actions only; no shared layout — each page still mounts the header).
  - `useQuery` for `GET /generated-emails` + `GET /outcomes` (first genuine read-only TanStack Query usage; contrast with §8.2.1 all-`useMutation` credit-spending mutations).
  - No `sessionStorage` on `/history` (deliberate contrast with `/` `discoveryFlow` — free idempotent reads, refetch on mount is correct).
  - Client-side group outcomes by `generated_email_id` (O(1) network for list+timeline, not O(n) per-row fetches); filter All / Logged / Not yet logged (default **Logged**).
  - Row expand via `<details>`: `getGeneratedEmailById` on first open; timeline from already-loaded outcomes; log any `OutcomeEventType` via existing `createOutcome`; retract via `retractOutcome` with inline two-click confirm.
  - API client additions: `listGeneratedEmails`, `getGeneratedEmailById`, `listOutcomes`, `retractOutcome`; `GeneratedEmailListOut` type; `OutcomeOut.voided` added (was missing on the frontend type).
- **Frontend tests run this session (all passed):**
  ```
  npm run test:run
  → Test Files  9 passed (9)
  → Tests  53 passed (53)
  ```
  History coverage: default Logged hides unlogged; All / Not yet logged toggles; expand fetches full email + shows timeline; log new event type updates timeline + badge; retract removes entry and drops row from default Logged filter when it was the last outcome.
  `tsc -b` clean.
- **Slice 2a backend (prior):** unchanged — `GET /generated-emails`, `POST /outcomes/{id}/retract`, `OutcomeOut.voided`, migration `c4f8e2a91b07`.
- **FRAME 6 Mark as Sent (Slice 1):** unchanged; separate surface.

### Present, but not yet exercised by anything

- **Manual browser dogfood of `/history`** — not done this session. Unit/integration tests cover the behaviors above against mocked fetch; live walkthrough against a running API (list, expand, log `replied`/`interview`, retract, filter disappearance) is still pending.
- **Router-level HTTP TestClient suites** for Slice 2a list/retract endpoints — still service-level only from 2a.

### Not started

- **Analytics view**, **Apollo/Anymail providers**, **refresh-token rotation / cookie transport / rate-limiting**, **public/live deployment**, **`GENERATED_EMAILS.user_id` denormalization**, **resume picker reuse**, **regenerate-email control**.

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
9. **sessionStorage key `discoveryFlow`:** `{ company, discoveryResult, resume, jobDescription, generatedEmail, sentOutcomeLogged }` — home flow only; `/history` deliberately has none.
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry`. Deterministic post-eval signature append + `_strip_trailing_closing`.
11. **`OUTCOMES.user_id` denormalized** (migration `75ea1b948b2a`); **`voided`** added (migration `c4f8e2a91b07`) — narrow retract exception to append-only; see `DATA_MODEL.md` §2.8 / `OPEN_QUESTIONS.md`.

---

## What's next

1. **Manual browser dogfood** of `/history` (and Mark as Sent + generated emails in real outreach).
2. **Analytics view** against `GET /outcomes` (must use `services/outcomes.py`).
3. **Stretch — rate-limiting** before any public deploy.

---

## Test results (this session — actual suite output)

```
frontend: npm run test:run
→ Test Files  9 passed (9)
→ Tests  53 passed (53)

frontend: npx tsc -b
→ exit 0 (clean)
```

**Not run this session:** full backend suite, live LLM/provider calls, manual browser walkthrough of `/history`.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for Slice 2b; explicit note that manual browser dogfood of `/history` is still pending.
- **`ARCHITECTURE.md`:** §8.1 routing updated for `/history`; §8.5 AppHeader nav; new §8.6 (no sessionStorage contrast with §8.2.2, `useQuery` contrast with §8.2.1, client-side grouping, filter default).
- **`OPEN_QUESTIONS.md`:** Slice 2 entry moved to Resolved (2a+2b done); analytics still future.
