import type {
  ContactDiscoveryResponse,
  LockedCompany,
  PersistedDiscoveryFlow,
} from './discoveryTypes'

/**
 * Namespaced sessionStorage key for the company-resolution + contact-discovery
 * flow. One JSON object ({ company, discoveryResult }) — not multiple keys.
 *
 * sessionStorage (not localStorage) is deliberate: a discovered contact's
 * name/email is third-party PII, not just the user's own data. sessionStorage
 * clears on tab close (bounded exposure); localStorage would leave it sitting
 * indefinitely.
 */
export const DISCOVERY_FLOW_KEY = 'discoveryFlow'

const EMPTY: PersistedDiscoveryFlow = {
  company: null,
  discoveryResult: null,
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
    }
  } catch {
    return EMPTY
  }
}

export function writeCompanyLock(company: LockedCompany): void {
  // Persist immediately on lock-in (before role_title) so a refresh during
  // FRAME 2 rehydrates to FRAME 2, not FRAME 1. Candidate lists from
  // /companies/search are intentionally NOT persisted — that call is free
  // (keyless Clearbit) and idempotent; re-running on refresh is fine.
  const payload: PersistedDiscoveryFlow = {
    company,
    discoveryResult: null,
  }
  sessionStorage.setItem(DISCOVERY_FLOW_KEY, JSON.stringify(payload))
}

export function writeDiscoveryResult(
  company: LockedCompany,
  discoveryResult: ContactDiscoveryResponse,
): void {
  // Persist on completed discovery — success OR contact: null. Both are valid
  // completed outcomes. POST /contacts/discover spends real, rationed provider
  // credits (Hunter: 50/month). Persisting so a refresh rehydrates FRAME 3
  // from storage (no re-fetch) is a correctness/cost concern, not UX polish.
  const payload: PersistedDiscoveryFlow = {
    company,
    discoveryResult,
  }
  sessionStorage.setItem(DISCOVERY_FLOW_KEY, JSON.stringify(payload))
}

export function clearDiscoveryFlow(): void {
  sessionStorage.removeItem(DISCOVERY_FLOW_KEY)
}
