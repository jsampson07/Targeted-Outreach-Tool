import type {
  ContactDiscoveryResponse,
  LockedCompany,
  PersistedDiscoveryFlow,
} from './discoveryTypes'
import type { JobDescriptionOut, ResumeOut } from './documentTypes'
import type { GeneratedEmailOut } from './generatedEmailTypes'

/**
 * Namespaced sessionStorage key for the home-page flow (company resolution,
 * contact discovery, resume/JD extract results, generated email, and the
 * local "sent" outcome UX flag). One JSON object — not multiple keys.
 *
 * sessionStorage (not localStorage) is deliberate: a discovered contact's
 * name/email is third-party PII, and extract/generate results are paid LLM
 * outputs. sessionStorage clears on tab close (bounded exposure); localStorage
 * would leave them sitting indefinitely.
 */
export const DISCOVERY_FLOW_KEY = 'discoveryFlow'

const EMPTY: PersistedDiscoveryFlow = {
  company: null,
  discoveryResult: null,
  resume: null,
  jobDescription: null,
  generatedEmail: null,
  sentOutcomeLogged: false,
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
      generatedEmail: parsed.generatedEmail ?? null,
      sentOutcomeLogged: parsed.sentOutcomeLogged === true,
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
  // New company lock clears discovery + document + email results.
  writeFlow({
    company,
    discoveryResult: null,
    resume: null,
    jobDescription: null,
    generatedEmail: null,
    sentOutcomeLogged: false,
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
  // Clear document/email fields: a new discovery starts a new search pipeline.
  writeFlow({
    company,
    discoveryResult,
    resume: null,
    jobDescription: null,
    generatedEmail: null,
    sentOutcomeLogged: false,
  })
}

export function writeResumeResult(
  company: LockedCompany,
  discoveryResult: ContactDiscoveryResponse,
  resume: ResumeOut,
): void {
  // Persist after successful upload+extract so refresh does not re-pay LLM.
  // A new resume invalidates any prior generated email for this search.
  const current = readDiscoveryFlow()
  writeFlow({
    company,
    discoveryResult,
    resume,
    jobDescription: current.jobDescription,
    generatedEmail: null,
    sentOutcomeLogged: false,
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
    generatedEmail: null,
    sentOutcomeLogged: false,
  })
}

export function writeGeneratedEmailResult(
  company: LockedCompany,
  discoveryResult: ContactDiscoveryResponse,
  resume: ResumeOut,
  jobDescription: JobDescriptionOut,
  generatedEmail: GeneratedEmailOut,
): void {
  // A new generated email resets the sent-outcome UX flag — confirmation
  // applies only to the email currently displayed on FRAME 6.
  writeFlow({
    company,
    discoveryResult,
    resume,
    jobDescription,
    generatedEmail,
    sentOutcomeLogged: false,
  })
}

/**
 * Mark that a "sent" outcome was logged for the current generatedEmail.
 * Frontend UX guard only — does not imply uniqueness on the backend.
 */
export function writeSentOutcomeLogged(): void {
  const current = readDiscoveryFlow()
  if (!current.generatedEmail) {
    return
  }
  writeFlow({
    ...current,
    sentOutcomeLogged: true,
  })
}

export function clearDiscoveryFlow(): void {
  sessionStorage.removeItem(DISCOVERY_FLOW_KEY)
}
