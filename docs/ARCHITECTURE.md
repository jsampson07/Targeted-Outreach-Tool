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

`eval.py`'s `evaluate_with_retry` owns the silent single-retry hard-gate orchestration from `product_discovery_summary.md` (evaluate → on gate failure, `refine` once with `violation_detail` → evaluate again → return the second pass either way). `gate_passed` / the retry trigger is the AND of **three** Tier 1 booleans (`no_unsupported_claims`, `correct_contact_name_used`, `no_unprompted_gap_admission`) — the third was added after dogfooding; `eval_prompt` instructs the judge to treat gap-admission as a tone/strategy failure distinct from factual unsupported claims. `refine(email, feedback) -> EmailDraft` remains the standalone reusable primitive so the deferred v1.1+ interactive multi-turn refinement path is more calls / more triggers / a UI, not a rebuild.

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

### 4.5 Dev fixtures for live mock mode

**Decision:** When `CONTACT_PROVIDER=mock`, the discovery router factory (`_build_providers` in `app/routers/contact_discovery.py`) constructs `MockProvider(scripted=DEV_SCRIPTED_RESULTS)`, not a bare `MockProvider()`. The scripted map lives in `app/providers/mock_fixtures.py`. Bare `MockProvider()` (empty default for unscripted domains) remains correct for unit tests that inject their own scripts.

**Why a separate fixtures module:** Service-level tests already pass per-test `scripted=` maps and never exercise the router factory. Without wiring fixtures at the factory, every manual/live discovery call under mock mode returned zero candidates for every domain — contradicting Phase 0's locked "mock/fixture provider simulating realistic scenarios" strategy.

**Manual testing domains** (fictional; Clearbit often won't suggest them — use FRAME 1's manual name+domain fallback):

| Domain | Scenario |
|---|---|
| `acme.com` | Tier-1 verified recruiter hit. `tier_used=recruiter`, no `fallback_reason`, high confidence. |
| `globex.com` | Empty recruiter + talent-acquisition tiers, then a pattern-guessed hiring-manager hit. Exercises `fallback_reason` + lower `best_verification_tier`. |
| `empty.co` | All four tiers empty on purpose. `contact=null` with the exhausted-tiers `fallback_reason` (not-found path). |

Any other domain still gets the bare default (successful empty candidates) unless added to `DEV_SCRIPTED_RESULTS`. After a successful find, Postgres cache (§5) may short-circuit a re-search for that domain until the contact row is cleared.

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

---

## 8. Frontend Architecture

**Decision:** Vite + React + TypeScript SPA under `frontend/`, with React Router for navigation, TanStack Query at the root for server-state, a thin shared `fetch` wrapper (`src/lib/apiClient.ts`) for HTTP, and React Context (`AuthContext`) for auth session state — not Redux/Zustand at this scale.

### 8.1 Routing

**Decision:** `react-router-dom` (`BrowserRouter`) with public `/login` `/signup` routes and a `ProtectedRoute` wrapper that redirects to `/login` when `!isAuthenticated`. A single persistent home route (`/`) hosts the product flow — company resolution, contact discovery, resume/JD upload+extract, and generated email — as accumulating frames/sections on that one page, **not** as one route per feature.

**Reasoning:** At this scale there is no serious alternative worth debating — React Router is the default for React SPAs, and the protected-route pattern matches the JWT-gated backend without inventing a custom gate. Flow steps (search → role title → discovery → resume → JD → generate email) are component state on `/`, not URL segments: deep-linking mid-flow is not a v1 need, and keeping one route avoids inventing a multi-step URL scheme for a linear demo flow.

### 8.2 Server state: TanStack Query

**Decision:** Wrap the app in `QueryClientProvider` from `@tanstack/react-query` at the root (`main.tsx`). Feature-screen calls that are user-triggered side effects use `useMutation`; auth login/signup stay on Context + imperative `apiClient` calls (form submit, token side effects) rather than being forced through Query.

**Reasoning:** Manual `useEffect` + `useState` per API call duplicates loading/error/retry handling across every data-fetching component — a real maintenance cost once company resolution, discovery, uploads, and email generation all hit the network, not just a style preference. The root provider was installed in the auth-foundation slice so feature screens opt into `useQuery`/`useMutation` without a second wiring pass.

**Alternative considered:** Skip TanStack Query until the first feature screen needs caching. Rejected because the root provider is cheap and the duplicated-boilerplate cost shows up immediately across multiple API-calling screens.

### 8.2.1 `useMutation` for company search, contact discovery, document extract, and email generation

**Decision:** `POST /companies/search`, `POST /contacts/discover`, resume upload+extract, JD create+extract, and `POST /generated-emails` are wired with TanStack Query `useMutation`, **not** `useQuery`.

**Reasoning:** These are side-effecting, user-triggered actions (submit a search; spend discovery credits; spend LLM extract/generate credits), not cacheable/refetchable reads. `useQuery` would imply background refetch, stale-while-revalidate, and remount-triggered re-execution — wrong for a Clearbit lookup that should fire once per submit, and actively harmful for discovery/extract/generate, which spend real, rationed credits. Mutation semantics (explicit `mutate`, no automatic refetch) match the product contract.

### 8.2.2 Discovery-flow sessionStorage persistence

**Decision:** Persist home-page flow state in `sessionStorage` under a single namespaced key `discoveryFlow`, storing one JSON object `{ company, discoveryResult, resume, jobDescription, generatedEmail }`. Do **not** use `localStorage` for this payload. Do **not** persist the raw company-search candidate list. Document and email fields were added to this same key (not a sibling) so "Start new search" and rehydration stay one clear/one read — see §8.2.3–§8.2.4.

**What is persisted:**
- On successful company lock-in (candidate click or manual domain entry): `{ company: { name, domain }, discoveryResult: null, resume: null, jobDescription: null, generatedEmail: null }` — written immediately, before `role_title` is entered, so a refresh during the role-title frame rehydrates there rather than back to company search.
- On discovery mutation completion (contact found **or** `contact: null` — both are valid completed outcomes): the full `ContactDiscoveryResponse` is written under the same object; document/email fields are cleared (new discovery starts a new pipeline).
- On successful resume/JD extract: the post-extract `ResumeOut` / `JobDescriptionOut` objects are written under `resume` / `jobDescription` (see §8.2.3).
- On successful email generation: the full `GeneratedEmailOut` is written under `generatedEmail` (see §8.2.4).

**What is not persisted:** The candidate list from `POST /companies/search`. That call is free (keyless Clearbit) and idempotent; re-running it after a refresh is fine and cheaper than storing ephemeral suggestion UI.

**Why sessionStorage over localStorage:** A discovered contact's name/email is third-party PII, not just the user's own data. `sessionStorage` clears on tab close (bounded exposure); `localStorage` would leave it sitting indefinitely. This is a deliberate choice, not a default.

**Why discovery persistence is a cost/correctness concern:** `POST /contacts/discover` spends real, rationed provider credits. If a refresh silently re-triggered discovery, credits would burn on an accidental reload. Rehydrating the result frame from storage (no re-fetch) prevents that. On mount, the home page reads `discoveryFlow` once via a lazy `useState` initializer and lands directly on the correct frame — no flash of the company-search frame. "Start new search" clears both component state and the `sessionStorage` key.

### 8.2.3 Resume + JD upload/extract frames (FRAME 4–5)

**Decision:** After contact discovery (FRAME 3), the same `/` page continues with resume upload+extract, then JD paste+extract, then generate-email (FRAME 6 — see §8.2.4). No new routes.

**Frame order (locked):** FRAME 1 company search → FRAME 2 role title → FRAME 3 discovery result → FRAME 4 resume → FRAME 5 JD → FRAME 6 generate email. Resume stays before JD: resume creation does not need `company_id`, and JD creation does. Ordering JD first would not make `company_id` available any earlier — see below.

**Backend contracts verified against routers/services (not docs alone):**
- **Resume create:** `POST /resumes` is **multipart** with form field `file` (PDF/DOCX). Server parses via pypdf/python-docx into `raw_text`, then persists. Not a JSON `ResumeCreate{raw_text}` body — that Pydantic model is an internal post-parse shape only.
- **Resume extract:** `POST /resumes/{resume_id}/extract` → `ResumeOut` (overwrites `extracted_data`).
- **JD create:** `POST /job-descriptions` JSON `{ raw_text, company_id, role_title }` → `JobDescriptionOut`.
- **JD extract:** `POST /job-descriptions/{jd_id}/extract` → `JobDescriptionOut`.
- **JD read:** `GET /job-descriptions/{jd_id}` → `JobDescriptionOut` (ownership-filtered; available for refetch-by-id).
- **Resume upload validation (server):** only `.pdf`/`.docx`; 2MB cap (`user_message`: `"File too large"`); min 50 chars extracted text after parse (scanned-image style message). Frontend mirrors extension + 2MB checks client-side; the 50-char rule remains server-only (depends on parse).

**`company_id` source:** Frame 1's locked company is `{ name, domain }` only — no id. Discovery's `get_or_create_company` creates/finds the row server-side, but `ContactDiscoveryResponse` only exposes `company_id` on a found `contact`. The JD step therefore uses `discoveryResult.contact.company_id`. When `contact` is null, FRAME 3 does not offer Continue (cannot create a JD frontend-only without a backend change to return `company_id` on empty discovery).

**`useResumeForGeneration` isolation boundary:** How a `resume_id` is obtained for generation is isolated in `hooks/useResumeForGeneration.ts`. Current internals are Option 2 — fresh multipart upload + extract every search (`useMutation`, create then extract). Callers consume `resume` / `resumeId` / `obtainFromUpload`. A future saved-resume picker (Option 3) should swap this hook's internals only — see `OPEN_QUESTIONS.md`.

**JD step:** paste `raw_text` + `role_title` (collected on FRAME 5, not reused from the discovery role-title field), `company_id` from the contact; `useMutation` for create+extract. Displays `JDExtraction` (`required_skills`, `responsibilities`, `seniority_level`).

**sessionStorage extension:** Added `resume` and `jobDescription` fields on the existing `discoveryFlow` object (not a sibling key). Same third-party-PII / paid-action reasoning as discovery: extract endpoints spend LLM credits; refresh must rehydrate the confirmation UI without re-calling `/extract`. Full post-extract Out objects are stored (mirrors storing full `ContactDiscoveryResponse`). `GET /job-descriptions/{id}` remains available if a later slice prefers id-only storage + refetch. FRAME 6 extends the same key with `generatedEmail` — see §8.2.4.

### 8.2.4 Generate-email frame (FRAME 6)

**Decision:** After FRAME 5's JD `extracted_data` is non-null (and the user continues), the same `/` page shows FRAME 6 — an explicit **Generate Email** button wired with `useMutation` (not auto-fired on frame entry). Contact existence is already guaranteed by this point: JD creation required a non-null contact's `company_id`. No new routes. No `mailto:` / send affordance — copy-paste only.

**Trigger condition:** FRAME 5 confirmation after successful JD extract (`extracted_data != null`), then an explicit continue into FRAME 6. Generation itself is a second explicit click — same credit-conscious pattern as discovery/extract.

**Backend contract verified against `backend/app/routers/generated_emails.py` + `backend/app/schemas/generated_email.py` (not docs alone):**
- **Path/method:** `POST /generated-emails` (router prefix `/generated-emails` + `POST ""`).
- **Request (`GenerateEmailRequest`):** `{ contact_id, resume_id, job_description_id }` — `contact_id` from Frame 3 discovery result, `resume_id` from `useResumeForGeneration` (public interface unchanged), `job_description_id` from Frame 5 `JobDescriptionOut.id`.
- **Response (`GeneratedEmailOut`):** `id`, `contact_id`, `resume_id`, `job_description_id`, `subject`, `body`, `eval_score`, `eval_breakdown` (`EvalBreakdownOut`), `match_data` (`MatchData`), **top-level** `gate_passed`, `created_at`.
- **`eval_breakdown.gates`:** `EvalGatesOut` — `no_unsupported_claims` + `correct_contact_name_used` + `no_unprompted_gap_admission` only. `violation_detail` is stripped at the API boundary on this Out shape (POST and GET-by-id); the client must not fabricate or infer it.
- **`match_data` fields:** `skill_matches`, `experience_alignment`, `unmatched_jd_requirements`, `notable_resume_strengths`, `overall_match_summary` — matches `MatchData` in `DATA_MODEL.md` §2.7.
- **Company/contact mismatch (422):** `ValidationError` → `{ user_message, error_code }`. Live `user_message`: `"Contact and job description must belong to the same company. Contact is tied to company_id=…; job description is tied to company_id=…."` Frontend surfaces `ApiError.user_message` (and offers Retry on failure before any success).

**Result display:**
- Primary content: `subject` + `body`.
- **Copy to clipboard:** one action copies paste-ready `"Subject: …\n\n<body>"`. Core to the copy-paste-only product — no send / mailto.
- **`eval_score`** plus a clear visual indicator when `gate_passed` is false (flagged state) so gate failure is glanceable, not just a bare number.
- **`eval_breakdown.dimensions`:** the five 1–5 scores; **`eval_breakdown.gates`:** the three booleans only.
- **`match_data`:** `overall_match_summary` inline by default; remaining fields inside a collapsed-by-default `<details>` section — mirrors the discovery-frame `confidence_breakdown` precedent (`OPEN_QUESTIONS.md` Resolved → "UI-level exposure of confidence_breakdown").

**Single-shot design:** Once a result exists (successful mutation **or** sessionStorage rehydration), FRAME 6 shows the result only — no Generate button again. A failed attempt (before any success) may show Retry. Regenerating after a successful result is out of scope for v1 — see `OPEN_QUESTIONS.md` Explicitly deferred.

**sessionStorage extension:** Added `generatedEmail: GeneratedEmailOut | null` on the existing `discoveryFlow` key (not a sibling). Same paid-call rehydration reasoning as resume/JD (§8.2.2–§8.2.3): generation spends LLM credits (match + generate + eval, possibly silent internal retry); refresh must not re-call `POST /generated-emails`.

### 8.3 API client and shared 401 handling

**Decision:** A single `request(path, options)` wrapper around `fetch` (not axios). Base URL from `import.meta.env.VITE_API_BASE_URL`. Attaches `Authorization: Bearer <access_token>` from localStorage when present. JSON bodies set `Content-Type: application/json`; `FormData` bodies are passed through without forcing that header (browser sets the multipart boundary). On non-2xx, throws an `ApiError` carrying the backend's `{user_message, error_code}` shape so UI code can surface `user_message` directly. On **401 when an Authorization header was actually sent**: clear both tokens from localStorage and `window.location.assign('/login')` — no refresh attempt.

**Reasoning:** One shared 401 path means callers never re-implement "session died" behavior. Refresh-on-401 is deliberately out of scope for this slice (redirect-to-login only); `POST /auth/refresh` exists on the backend but is unused here. The "Authorization was sent" guard matters because `/auth/login` also returns 401 for bad credentials — without it, a failed login would clear storage and force a full-page reload instead of showing `user_message` on the form.

**Backend contract verified against `app/routers/auth.py` / `app/schemas/auth.py`:**
- `POST /auth/signup` → `TokenPairOut` (201) — tokens returned immediately
- `POST /auth/login` → `TokenPairOut`
- `POST /auth/refresh` → `TokenPairOut` (body: `{refresh_token}`) — present, unused on 401
- `POST /auth/logout` → 204 (body: `{refresh_token}`) — client logout calls this, then clears localStorage

### 8.4 Token storage: localStorage

**Decision:** Persist `access_token` and `refresh_token` in `localStorage`.

**Reasoning / tradeoff:** Matches the backend's current JSON-body refresh transport (no httpOnly cookie). Any XSS that can run script in the origin can read those tokens — that is the concrete risk this choice accepts. This does **not** reopen or flip the deferred cookie-transport decision; it is the client-side half of the same simplicity choice. See `OPEN_QUESTIONS.md` ("Refresh-token transport") for the revisit trigger, which is no longer purely theoretical now that localStorage is the live storage mechanism.
