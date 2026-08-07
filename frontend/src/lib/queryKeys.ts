/** TanStack Query keys shared across history, analytics, and outcome mutations. */

export const GENERATED_EMAILS_QUERY_KEY = ['generated-emails'] as const

export const OUTCOMES_QUERY_KEY = ['outcomes'] as const

export const ANALYTICS_SUMMARY_QUERY_KEY = ['analytics', 'summary'] as const

export function generatedEmailDetailQueryKey(id: number) {
  return ['generated-emails', id] as const
}
