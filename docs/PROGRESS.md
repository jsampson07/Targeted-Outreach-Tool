# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-06 — analytics view (MVP feature #7).*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Analytics view (this session — MVP feature #7):**
  - Backend: `GET /analytics/summary` → `AnalyticsSummary` (schemas in `app/schemas/analytics.py`). Pure `_compute_summary` + thin `get_reply_rate_summary` in `app/services/analytics.py`. Outcomes via `list_outcomes` only; email/tier fields via new `list_generated_emails_for_analytics` in `generated_emails.py` (analytics never queries `Outcome` / `GeneratedEmail` / `Contact` directly).
  - Locked math: replied = distinct email with ≥1 non-voided `{REPLIED, INTERVIEW}` **and** a SENT; sent = distinct email with ≥1 non-voided SENT; tier = `best_verification_tier` as-is; eval buckets `"<3"`/`"3-4"`/`"4+"` with `[0,3)` / `[3,4)` / `[4,5]` boundaries; omit buckets with `sent==0`; `overall_reply_rate=None` when `total_sent==0`; no caching.
  - Frontend: protected `/analytics` (`AnalyticsPage`) + Analytics nav link on `AppHeader` (now Search / History / Analytics). `useQuery` + `getAnalyticsSummary()`; no `sessionStorage`. Overall rate with `n=`, two breakdown lists, zero-data "no sent emails" state, short sample-size caveat.
- **Backend tests run this session (analytics pure function):**
  ```
  .venv/bin/python -m pytest tests/services/test_analytics.py -q
  → 8 passed
  ```
  Covers: empty → null rate + empty lists; SENT-only → `reply_rate=0.0`; REPLIED+INTERVIEW dedup; INTERVIEW-alone counts; duplicate SENT dedup; no-SENT excluded; eval boundaries 3.0/4.0; zero-sent tier omitted.
- **Frontend tests run this session (all passed):**
  ```
  npm run test:run
  → Test Files  10 passed (10)
  → Tests  56 passed (56)
  ```
  Analytics coverage: overall rate + `n=` + both breakdowns; null-rate empty state (not 0%); omitted zero-sent buckets not invented client-side.
  `tsc -b` clean.
- **Prior slices unchanged:** `/history` Slice 2b, outcomes Slice 2a, FRAME 6 Mark as Sent.

### Present, but not yet exercised by anything

- **Manual browser dogfood of `/analytics`** — not done this session. Unit tests cover aggregation math and page rendering against mocked fetch; live walkthrough against a running API (log SENT/REPLIED on `/history`, confirm rates on `/analytics`) is still pending.
- **Manual browser dogfood of `/history`** — still pending from prior session.
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

**Doc/code check this session (no drift found to reconcile):** Before building, verified AppHeader was Search/History only (docs §8.5/§8.6 matched), router had `/` + `/history` only, and API clients use per-feature `*Api.ts` + `*Types.ts` + shared `request()` — analytics followed those live conventions. Nav/routing docs updated for Analytics.

---

## What's next

1. **Manual browser dogfood** of `/analytics` and `/history` (and Mark as Sent + generated emails in real outreach).
2. **Stretch — rate-limiting** before any public deploy.

---

## Test results (this session — actual suite output)

```
backend: .venv/bin/python -m pytest tests/services/test_analytics.py -q
→ 8 passed

frontend: npm run test:run
→ Test Files  10 passed (10)
→ Tests  56 passed (56)

frontend: npx tsc -b
→ exit 0 (clean)
```

**Not run this session:** full backend suite, live LLM/provider calls, manual browser walkthrough of `/analytics` or `/history`.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for analytics view; explicit note that manual browser dogfood of `/analytics` is still pending.
- **`ARCHITECTURE.md`:** §8.1 routing + §8.5 AppHeader nav updated for `/analytics`; new §10 (pure/orchestration split, entity-read discipline, locked math, no-cache, frontend).
- **`DATA_MODEL.md`:** new §2.10 AnalyticsSummary schemas — computed-on-read, no migration.
- **`OPEN_QUESTIONS.md`:** new deferred entries for cross-tab and date-range filtering; Slice 2 resolved note corrected; new Resolved entry for analytics view.
- **`product_discovery_summary.md`:** left as-is — MVP feature #7 description still accurate.
