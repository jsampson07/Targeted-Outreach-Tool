import { request } from './apiClient'
import type { AnalyticsSummary } from './analyticsTypes'

/**
 * Reply-rate summary for the current user. Backend contract (verified):
 * ``GET /analytics/summary`` → ``AnalyticsSummary``. Free idempotent read —
 * use ``useQuery``, not ``useMutation`` (same reasoning as /history).
 */
export function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return request<AnalyticsSummary>('/analytics/summary')
}
