import type { JobDescriptionOut, ResumeOut } from './documentTypes'
import type { GeneratedEmailOut } from './generatedEmailTypes'

/** Types mirroring backend CompanySearch* / ContactDiscovery* schemas. */

export type CompanySearchCandidate = {
  name: string
  domain: string
}

export type CompanySearchResponse = {
  candidates: CompanySearchCandidate[]
}

export type VerificationTier =
  | 'verified'
  | 'pattern_guessed'
  | 'catch_all'
  | 'unknown'

export type ConfidenceBreakdown = {
  verification_tier_score: number
  cross_provider_corroboration: boolean
  employment_currency_signal: string
  domain_check_passed: boolean
  name_collision_detected: boolean
}

export type ContactOut = {
  id: number
  company_id: number
  name: string | null
  title: string | null
  email: string | null
  best_verification_tier: VerificationTier
  confidence_score: number
  confidence_breakdown: ConfidenceBreakdown
}

export type ContactDiscoveryResponse = {
  contact: ContactOut | null
  fallback_reason: string | null
  tier_used: string | null
}

/** Locked-in company identity used across FRAME 2 / FRAME 3. */
export type LockedCompany = {
  name: string
  domain: string
}

/**
 * Single sessionStorage payload for the home-page flow (discovery + documents
 * + generated email + local sent-outcome UX flag). Key: "discoveryFlow" —
 * see discoverySession.ts.
 *
 * ``resume`` / ``jobDescription`` / ``generatedEmail`` hold paid-call Out
 * objects so a refresh rehydrates without re-spending LLM/provider credits.
 *
 * ``sentOutcomeLogged`` is a frontend-only UX guard: true after a successful
 * POST /outcomes { event_type: "sent" } for the current generatedEmail, so a
 * refresh shows the confirmed state instead of inviting a duplicate click.
 * Not a backend constraint — the API still allows multiple SENT rows.
 */
export type PersistedDiscoveryFlow = {
  company: LockedCompany | null
  discoveryResult: ContactDiscoveryResponse | null
  resume: ResumeOut | null
  jobDescription: JobDescriptionOut | null
  generatedEmail: GeneratedEmailOut | null
  sentOutcomeLogged: boolean
}
