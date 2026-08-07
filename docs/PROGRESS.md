# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-07 — history row expand-state fix.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **History row expand state (this session — frontend-only):**
  - Replaced native per-row `<details>` on `/history` with controlled React state: single `expandedId: number | null` on `HistoryPage`.
  - Accordion behavior: expanding a row sets `expandedId` to that id (implicitly collapsing any other); clicking the open row sets `null`.
  - Filter-tab change (All / Logged / Not yet logged) resets `expandedId` to `null` via `handleFilterChange` — expand state does not persist across tabs.
  - Expand panel uses CSS `grid-template-rows` (0fr → 1fr) + opacity transition; no animation library.
  - Detail fetch still `useQuery({ enabled })` — now `enabled={expanded}` / `row.id === expandedId`. Loading indicator gated on `enabled && isPending` so collapsed rows do not show a spurious "Loading email…".
  - Filtering logic unchanged (client-side All / Logged / Not yet logged; default Logged). Expanded content still subject/body + outcome timeline + log form + retract.
- **Frontend tests run this session:**
  ```
  npm run test:run
  → Test Files  10 passed (10)
  → Tests  58 passed (58)
  ```
  New coverage: single-expand accordion; expand resets on filter-tab change. Existing expand / log / retract / filter tests updated for non-`<details>` markup (`aria-expanded` on the summary button).
  `tsc -b` clean.
- **Prior slices unchanged:** `/analytics` (MVP #7), `/history` Slice 2b otherwise, outcomes Slice 2a, FRAME 6 Mark as Sent.

### Present, but not yet exercised by anything

- **Manual browser dogfood of `/history` expand animation** — unit tests cover accordion + filter-reset + detail fetch; live visual check of the CSS transition against a running app is still pending (can confirm in browser that open/close is smooth, not a snap).
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
11. **`OUTCOMES.user_id` denormalized** (migration `75ea1b948b2a`); **`voided`** added (migration `c4f8e2a91b07`) — narrow retract exception to append-only; see `DATA_MODEL.md` §2.8 / `OPEN_QUESTIONS.md`.

**Doc/code check this session:** Code matched the old §8.6 `<details>` pattern (root cause of the bugs). Docs updated to the new controlled-`expandedId` pattern. No schema/API drift.

---

## What's next

1. **Manual browser dogfood** of `/history` expand animation + accordion/filter-reset, then `/analytics` and Mark as Sent in real outreach.
2. **Stretch — rate-limiting** before any public deploy.

---

## Test results (this session — actual suite output)

```
frontend: npm run test:run
→ Test Files  10 passed (10)
→ Tests  58 passed (58)

frontend: npx tsc -b
→ exit 0 (clean)
```

**Not run this session:** backend suite, live LLM/provider calls, manual browser walkthrough of expand animation.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for history row expand-state fix.
- **`ARCHITECTURE.md`:** §8.6 Row expansion (and related `enabled:` wording) updated — controlled single-`expandedId`, CSS transition, reset on filter-tab change; old native `<details>` description replaced.
- **`DATA_MODEL.md`:** left as-is — no schema/API involvement.
- **`product_discovery_summary.md`:** left as-is — no MVP scope change.
- **`OPEN_QUESTIONS.md`:** no new entry — no genuine open question discovered (animation is plain CSS; no edge case worth flagging).
