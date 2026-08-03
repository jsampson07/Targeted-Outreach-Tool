import { request } from './apiClient'
import type {
  GenerateEmailRequest,
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
