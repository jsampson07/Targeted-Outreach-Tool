# Progress Snapshot

> For external readers: this is a living, session-overwritten implementation snapshot from active development — verified against the codebase each session, not a polished changelog or finished status report.

*Overwritten each session, not appended to. Reflects verified state as of the session ending 2026-08-05 — Inroad rebrand (naming + logo/favicon assets + persistent header lockup); no schema or behavioral pipeline changes.*

---

## Implemented so far

### Verified working (functionally exercised, not just present)

- **Inroad rebrand (this session — branding / static assets / copy):** Product renamed from "Targeted Outreach Tool" to **Inroad** with naming pattern locked (bare "Inroad" for package/nav wordmark; full form "Inroad: Targeted Outreach Platform" at first-contact surfaces; persistent header lockup with caption). Logo mark is a capital-"I" monogram on a teal squircle (`frontend/src/assets/logo.svg`). Favicon set generated via `sharp` (`npm run generate-favicons`) into `frontend/public/`. Wired into `index.html`, `AppHeader`, login/signup, README, FastAPI `/docs` title, `product_discovery_summary.md` H1. **No schema, architecture behavior, or pipeline logic changes** beyond new static assets + `sharp` as a frontend `devDependency` for one-off regeneration.
- **Anchor-then-sweep closing strip (prior):** `_strip_trailing_closing` between `evaluate_with_retry` and signature append.
- **Frontend FRAME 1–6**; auth; Postgres; Alembic (9 tables); Hunter/Mock discovery; LLM extract/match/generate/eval.

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

**No full suite run this session** — branding/docs slice. Header extraction confirmed safe vs existing tests (no assertions on `discovery-header` / `"Contact discovery"` heading). Login/signup tests key off submit button labels, not the old page `<h1>` text.

---

## Doc notes from this session

- **`PROGRESS.md`:** overwritten for this branding session.
- **`ARCHITECTURE.md`:** new §8.5 Brand assets (logo source, sharp generate script, favicon set, token palette).
- **`DATA_MODEL.md`:** explicit note — no schema change for the rebrand.
- **`OPEN_QUESTIONS.md`:** favicon gap not re-flagged (resolved). Added a short caveat on SVG `<text>` rasterization / no `.ico` fallback.
- **`product_discovery_summary.md`:** H1 renamed only.
- **`README.md`:** Inroad title + subtitle + logo embed; purpose copy preserved with name reference update.
