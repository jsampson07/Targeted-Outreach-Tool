# Open Questions & Deferred Items

*Things that were discussed but explicitly not decided, or decided-with-a-stated-trigger-to-revisit. Distinct from `product_discovery_summary.md`'s "Deferred Features" table, which covers product-scope decisions — this file covers architecture/implementation-level items that came up while designing the backend.*

---

## Explicitly deferred (a decision was made to postpone, with a stated trigger)

### Cache staleness / re-verification policy
The current design ("cache hit → return existing contact, done") has no rule yet for when a cached `CONTACTS` row is considered stale enough to re-query providers anyway. The confidence model's "employment-currency signal" is an input to *scoring* a contact — that's a different concern from a cache-*invalidation* policy for deciding when to re-search. Deferred until Phase 2, once real reconciliation data exists to design against, rather than guessing a TTL number now.

### LLM match-selection mechanism (ranked vs. free-form)
v1 uses free-form selection — the email-generation model picks which 2-3 `MatchData` points to feature, entirely on its own judgment, each time. A ranked/constrained alternative (pre-rank `skill_matches` by a relevance heuristic, instruct the model to prefer the top-ranked items) was considered and explicitly deferred, not rejected — it's more debuggable/reproducible but costs more code in the matching step. Revisit if free-form selection proves inconsistent or low-quality once real output can be observed.

### Redis / dedicated cache technology
Not adopted. Explicit trigger to revisit: a *measured* load test showing Postgres query latency on the `COMPANIES`/`CONTACTS` cache lookup becoming a real bottleneck — not a hypothetical future user count. See `ARCHITECTURE.md` §5.1 for full reasoning.

### UI-level exposure of `confidence_breakdown`
The schema exposes the full `ConfidenceBreakdown` object through the API (decided). Which subset of fields the frontend actually renders to the user is unresolved — explicitly called out as a UI-copy/design decision to make later, not a backend one.

### Refresh-token transport (JSON body vs. httpOnly cookie)
v1 ships refresh tokens as plain JSON in the request/response body — not as an httpOnly cookie. This is a deliberate simplicity choice: cookie storage would pull in `CORSMiddleware(allow_credentials=True)`, SameSite policy, and CSRF-exposure handling that this project's stated differentiators (resilience engineering, data reconciliation, applied LLM eval — see `product_discovery_summary.md`) don't need to spend time on right now. Authorization headers alone do not require credential-mode CORS the way cookies do, so `allow_credentials` stays False/omitted. Stated trigger to revisit: only if this app ever handles data sensitive enough to justify the added complexity, or if XSS risk on the frontend becomes concrete rather than theoretical.

### Login rate-limiting / brute-force protection
Not implemented. `/auth/login` and `/auth/signup` currently accept unbounded attempts. Named here so the gap is explicit rather than a silent omission (same documentation pattern as Redis and Gmail OAuth). Stated trigger to revisit: before any real deployment beyond personal use.

### Upload body-size enforcement (app-level check vs. transport-level limit)
The 2MB cap in `create_resume_from_upload` runs *after* Starlette has already fully received and spooled the multipart body — it stops an oversized file from being parsed/persisted, but not the cost of receiving it. No ASGI-level body-size middleware or reverse-proxy limit (e.g. nginx's `client_max_body_size`) exists yet. Named here so the gap is explicit rather than a silent omission (same pattern as login rate-limiting). Stated trigger to revisit: before any real deployment beyond personal use, or whenever a reverse proxy is introduced.

### JD deduplication / extraction-result caching
Not implemented. Every JD submission creates a new row, even if the underlying posting text is identical across users — no dedup or reuse. Storage cost of duplicated text is negligible and not the concern; the real cost this would guard against is redundant LLM extraction calls once Phase 3 exists. Not worth building against: extraction doesn't exist yet, and there's no real multi-user evidence of duplicate postings (v1's primary user is a single person). Deferred until both conditions are real: Phase 3 extraction is built and its actual per-call cost is known, and a second real user exists to make cross-user duplication an observed pattern rather than a hypothetical. If revisited, keying a unique index off a hash of the normalized raw_text (not company_id + role_title, which doesn't safely disambiguate different versions of a posting) is the safer lookup — mirrors the get-or-create pattern already used for COMPANIES.domain.

### Hunter Domain Search pagination / truncation

HunterProvider fetches at most 100 emails per domain (limit=100, no pagination — see PROGRESS.md Deviations #25) and does not log when a domain actually has more on file, so results are silently truncated past that cap. Deferred as low-risk for a v1 aimed at typical small/mid-size target companies. Stated trigger to revisit: before running live-key checkpoint validation against a large company, or immediately if a real search returns suspiciously few or unexpected candidates.

### JD read-access control
JOB_DESCRIPTIONS has user_id, but this task adds no GET route for it — the only response containing a JD's raw_text is the 201 returned to the same request that created it. Stated trigger to revisit: the moment any GET route is added that reads JOB_DESCRIPTIONS, it must filter on id AND user_id together in one query (same pattern already used for GET /resumes/{id}), not return rows to any authenticated caller regardless of ownership.

### Stubbed during the first discovery-pipeline build (defaulted, not designed)
- **Name-collision resolution**: detection is real; resolution is highest-tier-wins,
  first-returned as tiebreak. Revisit once real multi-candidate collisions are observed.
- **Confidence score formula**: initial weighted formula, unvalidated. Needs calibration
  once real reconciliation data exists — same caution as the LLM-judge calibration note.
- **Company.name for discovery-only creation**: naive placeholder derived from domain
  when no existing row exists. Superseded once §7's company-name-resolution endpoint
  is built and wired ahead of discovery.

---

## Not yet discussed (on the list, conversation hasn't reached them)

*(none currently — all previously listed items have been resolved during Phase 1 planning; see "Resolved" section below.)*

---

## Explored but never settled at all (pure brainstorming, no direction chosen)

*(none currently — the `company_domain: str`-only input question below was resolved; see "Resolved" section.)*

## Resolved

### `ContactProvider.search()` input shape: `company_domain: str` vs. a richer object
**Resolved (Phase 0/1 planning):** `company_domain: str` stays as-is — no change to the `ContactProvider` interface. The richer identifier (a user-typed company *name*) is handled by a new pre-pipeline resolution step, not inside the provider abstraction. See `ARCHITECTURE.md` §7 ("Company Name Resolution") and `DATA_MODEL.md` §2.4.1 for the full design. This was resolved by first testing whether the assumption even needed revisiting: real-world testing against Clearbit's Autocomplete API (chosen for the resolution step) confirmed it reliably returns name+domain pairs, and name-collision handling turned out to be better solved by human selection from a candidate list than by any richer machine-parseable input to the provider layer itself.

### JWT auth flow (access/refresh token strategy, expiry lengths)
**Resolved (Phase 1 planning):** Access token + refresh token, without refresh-token rotation or reuse-detection in v1. The access token is a short-lived, stateless JWT — validated by signature/expiry alone, no DB hit on every request. The refresh token is an opaque random string, *not* a JWT, persisted (hashed) in a dedicated `refresh_tokens` DB table (user_id, token_hash, expires_at, revoked_at). This split was chosen deliberately, not just for simplicity: a purely stateless refresh JWT can't be revoked before its natural expiry (logout wouldn't actually invalidate anything), and adding rotation/reuse-detection later would mean retrofitting persistence into a system that had none. A DB-backed refresh token from the start makes rotation a purely additive later change (mark the old row revoked, insert a new one) rather than a redesign — this was explicitly checked before locking the simpler v1 flow in. Rotation/reuse-detection itself remains deferred, with this as the stated trigger-readiness condition already satisfied whenever it's revisited. The `refresh_tokens` table itself is now formally part of the locked schema — see `DATA_MODEL.md` §2.9 (Pydantic schema) and §3.1/§3.6/§3.8 (migration placement, FK indexing, dependency order), added there as a direct follow-on to this resolution rather than left implied only here.

### FastAPI dependency injection setup (`get_db`, `get_current_user` in `core/deps.py`)
**Resolved (Phase 1 planning):** Locked as the standard pattern — `get_db` is a generator dependency yielding a SQLAlchemy session with try/finally close; `get_current_user` decodes the Bearer token via `OAuth2PasswordBearer`, confirms it's an access-type token (not a refresh token replayed against the wrong endpoint), and loads the user from the DB. Failures raise the domain-level `AuthenticationError` (see the error-handling resolution below) rather than `HTTPException` directly. No further design debate — this is convention, not a project-specific decision.

### General error-handling/exception conventions across routers
**Resolved (Phase 1 planning):** Extends the pattern already locked in `ARCHITECTURE.md` §6 (internal error detail and user-facing copy stay separate objects) rather than introducing a new convention. A small `AppException` hierarchy lives in `app/core/exceptions.py` (`NotFoundError`, `AuthenticationError`, `AuthorizationError`, `ValidationError`, `ProviderUnavailableError`, etc.), each declaring its own `status_code` and a safe `default_user_message`. Routers and services raise these directly; they never construct `HTTPException` ad hoc for a domain error. A single FastAPI exception handler registered in `main.py` translates any `AppException` into a consistent `{user_message, error_code}` JSON response, logging the internal `detail` but never serializing it to the client. (The response key was briefly named `detail` while being populated from `user_message`; it was renamed to `user_message` before any client depended on the old key, to avoid the naming collision with the internal `detail` attribute.)

### Config/settings management specifics (`pydantic-settings` structure, secret handling)
**Resolved (Phase 1 planning):** `pydantic-settings`'s `BaseSettings` in `app/core/config.py`, values sourced from a local `.env` file (DB URL, JWT secret key, provider API keys), wrapped in a cached `get_settings()` accessor so it's read once, not on every call. `.env` is gitignored; a `.env.example` with placeholder keys is checked into the repo. No further design debate — standard practice at this scale.

### CORS setup for frontend↔backend
**Resolved (Phase 1 planning):** `CORSMiddleware` allowing the local frontend dev server's origin in development, with the allowed origin(s) read from `settings` rather than hardcoded, so a deployed environment can use a different value with no code change. No further design debate — standard practice.


### role_title's effect on tiering
**Resolved:** Unused by discovery for now — all four tiers search fixed, generic
title lists regardless of role. Revisit only if the generic hiring-manager tier
proves too noisy in real use.

### Employment-currency signal (Hunter response shape inspected)
**Resolved (HunterProvider integration):** Hunter Domain Search *does* return date-like fields — `sources[].last_seen_on` / `extracted_on` (when the email was last/first observed on a public page) and `verification.date` (when Hunter last ran deliverability verification). None of these is an employment-currency signal: they speak to email-source freshness or SMTP-check recency, not whether the person still holds the listed role at the company. Fabricating `"current"` / `"stale"` from those fields would mislabel the confidence input. `contact_discovery.py` therefore keeps `employment_currency_signal = "unknown"` hardcoded. Revisit only if a future provider (or a richer Hunter product surface) exposes a real current-employment / last-title-change signal.