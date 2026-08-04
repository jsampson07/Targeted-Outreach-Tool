# Progress Snapshot

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-04 — second dogfooding catch on model-authored closing strip; anchor-then-sweep replaces consecutive bottom-up walk.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Anchor-then-sweep closing strip (this session — dogfood round 2):**
  - **Root cause:** Round-1 consecutive bottom-up walk stopped at the first non-matching bottom line. Real body `"Thanks,\nLooking forward to hearing from you."` left both lines intact; programmatic `"Best regards,\n{name}"` stacked again. Same problem class as round 1, found via continued personal use — the "real outcome data" differentiator doing real work, not just a talking point.
  - **Fix:** `_strip_trailing_closing` now finds the earliest `_is_closing_line` match in the last ≤3 non-blank window and sweeps from that anchor through end of body. Bare-`candidate_name` last line is a fallback anchor. `_is_closing_line` unchanged. Wiring (once, after `evaluate_with_retry`, before signature append) unchanged.
  - **Rejected:** expanding the closing-phrase list to cover trailing prose — whack-a-mole (same reasoning as rejecting a fixed enum for `EvalGates.violation_detail`).
- **Strip model-authored trailing closing (prior session — dogfood round 1):** deterministic strip before signature append; fourth eval gate rejected.
- **Resume projects + signature name; third eval hard gate; live mock discovery fixtures.**
- **Frontend FRAME 1–6**; **`GET /generated-emails/{id}`**, **`GET /job-descriptions/{jd_id}`**, auth, Postgres, Alembic (9 tables), Hunter/Mock discovery, LLM extraction/matching/generation/eval.

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
10. **`ResumeExtraction` revision:** `candidate_name` + `projects`/`ProjectEntry` with defaults for JSONB backward compat. Deterministic post-eval signature append; generation/refine prompts forbid model closings.
11. **Model-closing strip (rounds 1–2):** `_strip_trailing_closing` between `evaluate_with_retry` and signature append. Round 2 = anchor-then-sweep. Not a schema change; fourth eval gate and phrase-list expansion both explicitly rejected (see `ARCHITECTURE.md` §3 / `OPEN_QUESTIONS.md`).

---

## What's next

1. **Manual dogfood** of generated emails after this strip fix — confirm stacked closings / trailing-sentence-after-Thanks cases are gone.
2. **Revisit `candidate_name` source** if mis-extraction shows up often (OPEN_QUESTIONS trigger).
3. **Stretch — outcome logging / analytics**; deferred providers/auth hardening only if usage demands.

---

## Test results (this session — actual suite output)

**Backend** (`pytest tests/services/test_generated_emails.py -ra` from `backend/`):

```
=================== 6 failed, 22 passed, 1 warning in 4.87s ====================
```

Failed (pre-existing isolation leak — unchanged by this branch):

| File | Tests | Cause |
|---|---|---|
| `test_generated_emails.py` | 6 error-path tests (`wrong_owner_*`, `missing_contact`, `*_missing_extracted_data`, `company_mismatch`) | `assert GeneratedEmail.count() == 0` sees leftover committed rows. `pytest.raises(...)` still passes. |

All prior strip/signature assertions still passing, plus 4 new strip cases: `test_strip_trailing_closing_phrase_then_trailing_sentence`, `test_strip_trailing_closing_stacked_closings_plus_name`, `test_strip_trailing_closing_bare_candidate_name`, `test_strip_trailing_closing_anchor_not_bottom_most_sweeps_to_end`.

**Frontend:** not exercised this session (backend-only strip algorithm change).

---

## Doc notes from this session

- **`ARCHITECTURE.md` §3:** Decision (strip model-authored closing…) updated to describe anchor-then-sweep; round-2 root cause and why phrase-list expansion was rejected (whack-a-mole / same as `violation_detail` enum rejection).
- **`OPEN_QUESTIONS.md`:** existing Resolved entry amended with linked dogfooding round-2 finding — not a duplicate entry.
- **`PROGRESS.md`:** overwritten for this slice.
- **`product_discovery_summary.md`:** no change needed — implementation-level bug fix, not MVP-scope or roadmap.
- **`DATA_MODEL.md`:** no change needed — no schema/column change.
