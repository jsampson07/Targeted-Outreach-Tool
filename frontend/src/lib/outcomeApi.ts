import { request } from './apiClient'
import type { OutcomeCreate, OutcomeOut } from './outcomeTypes'

/**
 * Append an outcome event for a generated email. Backend contract (verified):
 * ``POST /outcomes`` with ``OutcomeCreate`` → ``OutcomeOut`` (201).
 * Append-only — multiple SENT rows for the same email are allowed by design.
 */
export function createOutcome(payload: OutcomeCreate): Promise<OutcomeOut> {
  return request<OutcomeOut>('/outcomes', {
    method: 'POST',
    body: payload,
  })
}
