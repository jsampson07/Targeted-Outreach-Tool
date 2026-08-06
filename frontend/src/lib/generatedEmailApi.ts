import { request } from './apiClient'
import type {
  GenerateEmailRequest,
  GeneratedEmailListOut,
  GeneratedEmailOut,
} from './generatedEmailTypes'

/**
 * Generate + persist an outreach email. Backend contract (verified):
 * ``POST /generated-emails`` with ``GenerateEmailRequest`` → ``GeneratedEmailOut``.
 * Spends LLM credits (match + generate + eval, possibly silent retry).
 */
export function generateEmail(
  payload: GenerateEmailRequest,
): Promise<GeneratedEmailOut> {
  return request<GeneratedEmailOut>('/generated-emails', {
    method: 'POST',
    body: payload,
  })
}

/**
 * List past generated emails for the current user. Backend contract (verified):
 * ``GET /generated-emails`` → ``GeneratedEmailListOut[]``. Free idempotent read;
 * no outcome-status join (cross-reference GET /outcomes client-side).
 */
export function listGeneratedEmails(): Promise<GeneratedEmailListOut[]> {
  return request<GeneratedEmailListOut[]>('/generated-emails')
}

/**
 * Full generated-email row by id. Backend contract (verified):
 * ``GET /generated-emails/{id}`` → ``GeneratedEmailOut``. Used on /history
 * row expand for subject/body (list endpoint omits those).
 */
export function getGeneratedEmailById(
  id: number,
): Promise<GeneratedEmailOut> {
  return request<GeneratedEmailOut>(`/generated-emails/${id}`)
}
