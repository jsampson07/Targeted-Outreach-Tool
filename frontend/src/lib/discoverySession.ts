import type {
  ContactDiscoveryResponse,
  LockedCompany,
  PersistedDiscoveryFlow,
} from './discoveryTypes'
import type { JobDescriptionOut, ResumeOut } from './documentTypes'

/**
 * Namespaced sessionStorage key for the home-page flow (company resolution,
 * contact discovery, resume/JD extract results). One JSON object — not
 * multiple keys.
 *
 * sessionStorage (not localStorage) is deliberate: a discovered contact's
 * name/email is third-party PII, and extract results are paid LLM outputs.
 * sessionStorage clears on tab close (bounded exposure); localStorage would
 * leave them sitting indefinitely.
 */
export const DISCOVERY_FLOW_KEY = 'discoveryFlow'

const EMPTY: PersistedDiscoveryFlow = {
  company: null,
  discoveryResult: null,
  resume: null,
  jobDescription: null,
}

export function readDiscoveryFlow(): PersistedDiscoveryFlow {
  try {
    const raw = sessionStorage.getItem(DISCOVERY_FLOW_KEY)
    if (!raw) {
      return EMPTY
    }
    const parsed = JSON.parse(raw) as Partial<PersistedDiscoveryFlow>
    return {
      company: parsed.company ?? null,
      discoveryResult: parsed.discoveryResult ?? null,
      resume: parsed.resume ?? null,
      jobDescription: parsed.jobDescription ?? null,
    }
  } catch {
    return EMPTY
  }
}

function writeFlow(payload: PersistedDiscoveryFlow): void {
  sessionStorage.setItem(DISCOVERY_FLOW_KEY, JSON.stringify(payload))
}

export function writeCompanyLock(company: LockedCompany): void {
  // Persist immediately on lock-in (before role_title) so a refresh during
  // FRAME 2 rehydrates to FRAME 2, not FRAME 1. Candidate lists from
  // /companies/search are intentionally NOT persisted — that call is free
  // (keyless Clearbit) and idempotent; re-running on refresh is fine.
  // New company lock clears discovery + document results for this search.
  writeFlow({
    company,
    discoveryResult: null,
    resume: null,
    jobDescription: null,
  })
}

export function writeDiscoveryResult(
  company: LockedCompany,
  discoveryResult: ContactDiscoveryResponse,
): void {
  // Persist on completed discovery — success OR contact: null. Both are valid
  // completed outcomes. POST /contacts/discover spends real, rationed provider
  // credits (Hunter: 50/month). Persisting so a refresh rehydrates FRAME 3
  // from storage (no re-fetch) is a correctness/cost concern, not UX polish.
  // Clear document fields: a new discovery starts a new search pipeline.
  writeFlow({
    company,
    discoveryResult,
    resume: null,
    jobDescription: null,
  })
}

export function writeResumeResult(
  company: LockedCompany,
  discoveryResult: ContactDiscoveryResponse,
  resume: ResumeOut,
): void {
  // Persist after successful upload+extract so refresh does not re-pay LLM.
  const current = readDiscoveryFlow()
  writeFlow({
    company,
    discoveryResult,
    resume,
    jobDescription: current.jobDescription,
  })
}

export function writeJobDescriptionResult(
  company: LockedCompany,
  discoveryResult: ContactDiscoveryResponse,
  resume: ResumeOut,
  jobDescription: JobDescriptionOut,
): void {
  writeFlow({
    company,
    discoveryResult,
    resume,
    jobDescription,
  })
}

export function clearDiscoveryFlow(): void {
  sessionStorage.removeItem(DISCOVERY_FLOW_KEY)
}
