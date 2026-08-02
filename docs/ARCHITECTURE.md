# Architecture Reference

*Companion to `product_discovery_summary.md`, which remains the source of truth for product scope, MVP feature set, tech stack, and the eval rubric. This document covers the architectural and implementation decisions made when translating that scope into a concrete backend design. Organized by topic, not by when each decision was made.*

---

## 1. Repository Structure

**Decision:** Single monorepo with `backend/` and `frontend/` as top-level siblings, rather than two separate repos.

**Reasoning:** For a solo developer building a full-stack resume project, one clone and one README beats context-switching between repos. Nothing is deployed independently or owned by a separate team, so the usual reason to split (independent CI/CD, separate ownership) doesn't apply.

**Alternative considered:** Separate frontend/backend repos — the more common pattern in real organizations with independent deploy pipelines and team ownership. Rejected as pure overhead at this scale, but worth knowing as the "why" if asked in an interview.

---

## 2. Backend Folder Structure

**Decision:** Layer-based structure under `backend/app/`: `core/`, `db/`, `models/`, `schemas/`, `routers/`, `services/`, `providers/`, `llm/`, with `alembic/` and `tests/` as siblings of `app/`.

```
backend/
├── alembic/
│   ├── versions/
│   └── env.py
├── alembic.ini
├── app/
│   ├── main.py
│   ├── core/          # config.py, security.py, deps.py
│   ├── db/             # base.py, session.py
│   ├── models/         # SQLAlchemy ORM, one file per entity
│   ├── schemas/         # Pydantic — API I/O and LLM structured-output schemas
│   ├── routers/         # thin — parse request, call a service, return response
│   ├── services/        # business logic
│   ├── providers/       # ContactProvider interface + implementations
│   └── llm/             # client.py, prompts.py
└── tests/
```

**Reasoning:** Standard, immediately legible FastAPI convention — important for an interviewer opening the repo cold. At 7 entities and one developer, the structure needs to be easy to navigate, not optimized for large-team change isolation.

**Alternative considered:** Feature/domain-based structure (`features/contacts/{router,service,model,schema}.py`, one folder per domain). This earns its keep in larger or multi-team codebases where localizing change to one feature matters. Rejected here because several services (e.g. `contact_discovery.py`) span multiple entities (`Company`, `Contact`, `RawProviderResult`) and don't map cleanly onto a single feature folder, and because layer-based is more legible at this scale.

### Sub-decisions within the folder structure

- **`models/` and `schemas/` are separate packages.** SQLAlchemy models describe what's persisted in Postgres; Pydantic schemas describe what's allowed to cross a boundary (API request/response, or LLM structured output). Collapsing them risks leaking DB-only columns (e.g. a password hash) straight into API responses, since FastAPI will serialize whatever attributes it can reach on an object with no explicit `response_model` allowlist. It also breaks down for schemas with no backing table at all (`ResumeExtraction`, `EvalResult`, `MatchData`) — this isn't a gap, it's evidence those schemas are doing validation/boundary work rather than storage work. This is a correctness-adjacent convention, not pure style.
- **`providers/` is its own top-level package**, not nested inside `services/`. The multi-provider abstraction is the product's "hero problem," so giving it a dedicated package makes the interface/implementation seam visible in the repo layout itself.
- **Routers are thin, services are thick.** Routers parse the request, call a service function, and return the result — no business logic. This means services (e.g. `contact_discovery.py`, `generated_emails.py`) can be unit-tested directly, with no HTTP layer or test client involved, which matters given how much debugging is expected to happen in the discovery/reconciliation logic (per the roadmap's Phase 2 note) and in the generate→evaluate→persist orchestration.
- **`alembic/` sits next to `app/`, not inside it.** Migrations are infrastructure, not application code; `env.py` imports `app.db.base` to find model metadata, but the directory itself stays a sibling. This one is closer to pure convention — nothing breaks if nested differently, as long as `env.py`'s import path is correct.

---

## 3. LLM Client: Shared Thin Wrapper

**Decision:** A single `app/llm/client.py` wrapper (`LLMClient.complete(...)`) is called by all LLM-touching services rather than each service making its own direct call to the Anthropic API. There will eventually be **four** such services:

| Service | Role |
|---|---|
| `extraction.py` | Single-document structured extraction (resume → `ResumeExtraction`, JD → `JDExtraction`) |
| `matching.py` | Match/gap analysis comparing a `ResumeExtraction` to a `JDExtraction` → `MatchData` |
| `email_generation.py` | Grounded outreach draft from contact context + `MatchData` → `EmailDraft` |
| `eval.py` | Rubric-based judging of a generated email (`evaluate_email` / `refine` / `evaluate_with_retry`) |

`matching.py` is its own file because match/gap analysis is a **comparison between two already-extracted documents**, not a single-document extraction (so it does not belong in `extraction.py`) and not something `eval.py` should be responsible for producing (`eval.py` *consumes* `MatchData` as a verification reference — see `DATA_MODEL.md` §2.7).

`eval.py`'s `evaluate_with_retry` owns the silent single-retry hard-gate orchestration from `product_discovery_summary.md` (evaluate → on gate failure, `refine` once with `violation_detail` → evaluate again → return the second pass either way). `refine(email, feedback) -> EmailDraft` remains the standalone reusable primitive so the deferred v1.1+ interactive multi-turn refinement path is more calls / more triggers / a UI, not a rebuild.

**Reasoning:** All four call sites share the same underlying shape: prompt in, Pydantic-validated JSON out. This shared shape is already known from the product doc (structured extraction, match analysis, grounded generation, rubric-based judging all follow the same pattern) — it isn't a guess about future needs, which is what would normally argue for waiting. A shared wrapper gives one place to swap models, add retry/timeout/backoff logic, and log token usage/cost across all call sites, and lets tests substitute a fake client (mirroring the `mock.py` provider pattern) instead of monkeypatching HTTP calls in multiple files.

**Alternatives considered:**
- *Each service hits the Anthropic API directly.* Simpler per-file, but duplicates request-building and response-parsing logic, and any fix (timeout, retry, logging) has to be applied in multiple places — a real risk of silent drift, not just a style cost.
- *Skip the wrapper for now, write direct calls, refactor once patterns are clear.* Reasonable when the shared shape is genuinely uncertain. Rejected here specifically because the shape is *already* certain (all call sites specified in the product doc as the same prompt-in/validated-JSON-out pattern), so deferring would mean paying refactor cost later for zero information gained in the meantime — and that refactor would land during Phase 3, the highest-iteration-pressure phase per the roadmap.

**Cost accepted:** An extra layer of indirection. If one call site later needs a meaningfully different call shape (e.g. multi-turn), the wrapper either grows conditional params or gets bypassed for that one case — worth watching for, but not a blocker today.

---

## 4. `ContactProvider` Interface

**Decision:** An abstract base class (`ABC` + `@abstractmethod`) in `app/providers/base.py`, implemented identically by `HunterProvider`, `ApolloProvider`, `AnymailProvider`, and `MockProvider`.

```python
class ContactProvider(ABC):
    name: str

    @abstractmethod
    async def search(
        self, company_domain: str, role_titles: list[str]
    ) -> ProviderSearchResult:
        ...
```

**Reasoning (ABC over Protocol):** All four implementations are owned in-repo (not third-party objects being typed structurally), Python should error at class-definition time if a subclass forgets to implement `search()`, and shared helper methods (e.g. retry timing) can live on the base class. Protocol (structural typing) is the right tool when typing objects you don't own; ABC is the right tool when you own every implementation and want enforced inheritance.

### 4.1 Expected failures use a status-result object, not exceptions

**Decision:** `ContactProvider.search()` never raises for rate limits, auth/network failures, or zero matches. It always returns a `ProviderSearchResult` with a `status` field (`SUCCESS`, `RATE_LIMITED`, `ERROR`). A successful call that finds zero candidates is still `SUCCESS` — there's no separate `NO_RESULTS` status, since an empty-but-successful call is meaningfully different from a call whose outcome is unknown (`RATE_LIMITED`/`ERROR`), and `len(candidates) == 0` already distinguishes it cheaply.

**Reasoning:** These failure modes are expected and frequent (especially on free-tier rate limits), not exceptional. Using exceptions as the primary branching mechanism for something that happens on a large fraction of calls would mean a different try/except around every provider call in the orchestrator. A status field turns "handle every provider's failure modes" into one small, reusable, testable branch shared by all four providers, and it preserves context (which tier, what the other providers said) that gets lost if an exception propagates up from deep in a call stack. Each provider implementation is responsible for catching its own HTTP/network exceptions internally and translating them into a status — exceptions are still reserved for genuinely unexpected failures (e.g. malformed data the provider library itself can't parse).

**UX implication:** `ProviderSearchResult.error_message` is internal/debug-only and is never serialized to the frontend. The orchestrator translates provider statuses into a separate, user-facing schema (e.g. `ContactDiscoveryResponse.fallback_reason`) with hand-written, plain-language copy — this is what implements the product doc's "transparent, plain-language reason shown whenever it has to fall back" requirement.

### 4.2 Tiering logic lives in the orchestrator, not the provider

**Decision:** The recruiter → generalist TA → hiring manager → founder/CEO fallback sequence is owned entirely by `contact_discovery.py`. Each call to `provider.search()` represents one tier's attempt, taking that tier's acceptable titles as input; the provider has no awareness that other tiers exist.

**Reasoning:** Tiering is a business strategy independent of which provider is being called. Baking it into each provider would triplicate the sequencing logic and couple it to provider-specific quirks.

### 4.3 Caching logic lives in the orchestrator, not the provider

**Decision:** No `ContactProvider` implementation has a database handle or any awareness that a cache exists. `contact_discovery.py` is the only module that reads or writes `COMPANIES`/`CONTACTS`.

**Reasoning:** Same responsibility-boundary logic as tiering — see Section 5 for the full caching design. Stated explicitly here so it doesn't creep back into a provider implementation later: a cache check inside e.g. `HunterProvider.search()` would be a sign the boundary slipped.

### 4.4 Supporting schemas

```python
class VerificationTier(str, Enum):
    VERIFIED = "verified"
    PATTERN_GUESSED = "pattern_guessed"
    CATCH_ALL = "catch_all"
    UNKNOWN = "unknown"

class ProviderStatus(str, Enum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"

class ProviderCandidate(BaseModel):
    name: str | None
    title: str | None
    email: str | None
    verification_tier: VerificationTier
    raw_response: dict

class ProviderSearchResult(BaseModel):
    provider_name: str
    status: ProviderStatus
    candidates: list[ProviderCandidate] = []
    error_message: str | None = None
```

`ProviderCandidate` deliberately mirrors the `RAW_PROVIDER_RESULTS` table's columns almost 1:1 (see `DATA_MODEL.md`) — it *is* what becomes a row in that table, one row per candidate. `VerificationTier` lives in a neutral shared location rather than being defined separately in `models/` and `schemas/`, since both the SQLAlchemy column and the Pydantic schema need to reference the same enum without risk of drift.

**Assumption (not fully re-confirmed — see uncertainties):** `search()` takes `company_domain: str` rather than a richer object (name + domain + LinkedIn URL). Domain was chosen because all three real providers key off it reliably, whereas name-based search is more collision-prone.

**This design is what makes mock-first development real, not a workaround.** Because `MockProvider` implements the exact same ABC and returns the exact same `ProviderSearchResult` shape as the real providers, `contact_discovery.py` genuinely cannot tell mock from real — it's a full peer implementation, not a stub with a different shape to swap out later.

---

## 5. Caching Strategy

**Decision:** The "cache" is not a separate technology — it is the `COMPANIES` and `CONTACTS` Postgres tables, queried in a particular order: check for an existing usable contact before calling any provider; write results back after providers respond and reconciliation runs.

```python
# read (cache check) — inside contact_discovery.py only
existing = db.query(Contact).join(Company).filter(
    Company.domain == company_domain
).first()
if existing and existing.best_verification_tier != VerificationTier.UNKNOWN:
    return existing  # cache hit, zero provider credits spent

# write (after providers respond + reconciliation)
db.add(new_contact)
db.commit()
```

**Reasoning:** "Cache" describes a pattern of use (check somewhere cheap before doing something expensive), not a required data structure. Postgres already gives you persistence across restarts, safety across multiple worker processes, and — critically, per the product doc's explicit design goal — true cross-user sharing (`COMPANIES`/`CONTACTS` are deliberately not user-scoped, "to enable cross-user credit savings"). An in-memory structure (e.g. a module-level dict) would fail on all three counts: it resets on every restart, isn't shared across worker processes, and is *more* isolated than user-scoped data, not less — the opposite of the stated goal.

**What makes the lookup actually fast:** `Company.domain` must carry a unique index. Without it, the "cache" still functions but stops paying off as the table grows, since Postgres would have to scan every row to find a match.

### 5.1 Redis: not adopted

**Decision:** No Redis or other dedicated cache technology is introduced. Postgres with an indexed lookup is the caching layer, including under a "design for other users" framing.

**Reasoning:**
- The product's multi-user design is already handled by the shared (non-user-scoped) `COMPANIES`/`CONTACTS` tables — that mechanism works identically whether there are 2 users or 200,000, because it was designed around shared *data*, not around request volume.
- Redis earns its place when the data store itself is a measured bottleneck under real request *volume* — a function of requests/sec, not total user count. Nothing about this product's usage pattern (deliberate, low-frequency outreach searches, not a high-throughput consumer app) suggests that threshold is close, and no load testing has shown otherwise.
- Redis adds a second stateful system with its own failure modes and a real cache-invalidation problem (a `CONTACTS` write with no matching Redis invalidation silently produces stale reads) — trading a single source of truth for a new class of consistency bug, in exchange for solving a problem that hasn't been observed.
- If the pipeline does have a real bottleneck, it's far more likely to be third-party provider rate limits (Hunter's 50 credits/month, etc.) or LLM latency — not an indexed point-lookup on `Company.domain`. Redis wouldn't address the actual scarce resource.
- Demonstrating the judgment to *not* add infrastructure ahead of evidence is itself part of the product doc's stated differentiator (reasoned "why I didn't build X" decisions) — this mirrors the Gmail OAuth and `SEARCHES` table deferrals already locked in the product doc.

**Trigger condition for revisiting:** A measured (not hypothetical) load test showing Postgres query latency on the cache lookup becoming a real bottleneck. Because caching logic is fully isolated to `contact_discovery.py` (per Section 4.3), introducing Redis later would be a localized change to one module, not a rewrite — deferring costs effectively nothing.

**Alternative considered and rejected:** Adding Redis preemptively "because it's proven and fast" or because a hypothetical future user count might need it. Rejected as optimizing for an unmeasured bottleneck, at real ongoing cost (a new service to run, monitor, and keep consistent).

---

## 6. Error Translation Pattern (general, beyond `ContactProvider`)

**Decision:** Internal status/error detail (provider statuses, raw exception messages) and user-facing explanation are always distinct objects. The orchestrator layer is responsible for translating the former into hand-written, plain-language copy in the latter — never passing an internal error string through to the API response directly.

**Reasoning:** Keeps debugging information (logs, `error_message` fields) separate from product-quality copy the user actually sees, and is what allows the discovery-fallback UX ("no dedicated recruiter found, showing the hiring manager instead") to read as a designed product feature rather than an exposed internal state.

---

## 7. Company Name Resolution

**Decision:** A separate, thin service — e.g. `app/services/company_resolution.py` — resolves a user-typed company *name* into a domain, ahead of `contact_discovery.py`. It is deliberately **not** a `ContactProvider` implementation.

**Reasoning:** This service resolves company identity, not person/contact data — a different problem than anything §4 was designed around. It has no tiering (§4.2), no shared credit budget with Hunter/Apollo/Anymail, and fires once per submitted search rather than once per discovery-pipeline tier. Forcing it into the `ContactProvider` ABC would blur a boundary that's currently clean: `ContactProvider` implementations all answer "who is the contact at this known company," while this service answers a prior question, "which company is this, exactly." Its output (a resolved `company_domain`) feeds into the existing pipeline completely unchanged — `ContactDiscoveryRequest` and everything downstream of it are untouched by this addition.

**Mechanism:** Wraps a single call to Clearbit's Autocomplete API (`https://autocomplete.clearbit.com/v1/companies/suggest`), a free, keyless endpoint that returns candidate `{name, domain}` pairs (its `logo` field was deprecated to `null` in September 2025 and isn't used here). The service follows the same status-result pattern as §4.1 — it does not raise for zero matches or provider failure, and returns a result object the frontend can render directly:

```python
class CompanySearchRequest(BaseModel):
    query: str  # raw user-typed company name

class CompanySearchCandidate(BaseModel):
    name: str
    domain: str

class CompanySearchResponse(BaseModel):
    candidates: list[CompanySearchCandidate]
```

**UX contract:**
- The user always explicitly selects a candidate — resolution is never automatic, even when exactly one candidate is returned. This closes off a wrong-but-plausible top hit silently flowing into the (comparatively expensive) discovery pipeline.
- Both "zero candidates returned" and "the Clearbit call itself failed" (timeout, rate-limited, network error) route to the same user-facing fallback: a "Haven't found what you're looking for?" affordance that lets the user type the domain in directly. Per the §6 error-translation pattern, the two cases can carry different internal log detail even though the user-facing action is identical.
- v1 fires this call once per submitted search (on-submit), not on every keystroke. Live, debounced typeahead is a deferred, frontend-only enhancement — see `product_discovery_summary.md`'s Deferred Features table — since it adds request-race handling (a stale in-flight response for an earlier keystroke arriving after a newer one) that on-submit avoids entirely, and Clearbit's real rate limits haven't been load-tested yet.

**Known limitation, accepted for v1:** Clearbit's Autocomplete dataset has a real coverage gap for very recently founded/launched companies (empirically confirmed — a company that publicly launched roughly seven weeks prior to testing did not resolve). This is expected to be rare for this product's actual usage pattern (most applicants target established companies with an existing job posting and careers page), and it's exactly what the manual-domain fallback exists to catch. Not treated as a blocker; worth revisiting only if real usage shows this gap hit often in practice.

**Alternative considered:** Checking whether Apollo (already a paid, budgeted provider for the core pipeline) exposes its own organization-search-by-name endpoint, avoiding a fourth external dependency entirely. Not ruled out — genuinely unverified against Apollo's actual API surface — just not pursued yet in favor of shipping with Clearbit first.
