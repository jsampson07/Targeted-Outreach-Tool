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

/**
 * List non-voided outcomes for the current user. Backend contract (verified):
 * ``GET /outcomes`` with optional ``generated_email_id`` → ``OutcomeOut[]``.
 * Call with no filter for the full history used by /history.
 */
export function listOutcomes(
  generatedEmailId?: number,
): Promise<OutcomeOut[]> {
  const path =
    generatedEmailId === undefined
      ? '/outcomes'
      : `/outcomes?generated_email_id=${generatedEmailId}`
  return request<OutcomeOut[]>(path)
}

/**
 * One-way soft-delete: sets voided=true. Backend contract (verified):
 * ``POST /outcomes/{outcome_id}/retract`` → ``OutcomeOut``. Idempotent if
 * already voided.
 */
export function retractOutcome(outcomeId: number): Promise<OutcomeOut> {
  return request<OutcomeOut>(`/outcomes/${outcomeId}/retract`, {
    method: 'POST',
  })
}
