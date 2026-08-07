import { useQuery } from '@tanstack/react-query'

import { AnalyticsBreakdownList } from '../components/AnalyticsBreakdownList'
import { AppHeader } from '../components/AppHeader'
import { useAuth } from '../context/AuthContext'
import { getAnalyticsSummary } from '../lib/analyticsApi'
import { ApiError } from '../lib/apiClient'
import { ANALYTICS_SUMMARY_QUERY_KEY } from '../lib/queryKeys'

function formatOverallRate(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

/**
 * /analytics — reply rate overall + by confidence tier + by eval-score bucket.
 *
 * Deliberately does NOT use sessionStorage (same contrast with / as /history):
 * GET /analytics/summary is a free, idempotent read; refetch on mount is correct.
 */
export function AnalyticsPage() {
  const { logout } = useAuth()

  const summaryQuery = useQuery({
    queryKey: ANALYTICS_SUMMARY_QUERY_KEY,
    queryFn: getAnalyticsSummary,
  })

  const loadError =
    summaryQuery.error instanceof ApiError
      ? summaryQuery.error.user_message
      : summaryQuery.isError
        ? 'Something went wrong. Please try again.'
        : null

  const summary = summaryQuery.data

  return (
    <main className="home-page discovery-page analytics-page">
      <AppHeader
        actions={
          <button type="button" onClick={() => void logout()}>
            Log out
          </button>
        }
      />

      <h1 className="history-heading">Outreach analytics</h1>
      <p className="discovery-lead analytics-caveat">
        Early sample sizes are usually small — treat these rates as directional
        signals for your own outreach, not statistically significant findings.
      </p>

      {summaryQuery.isPending ? (
        <p className="discovery-muted" role="status">
          Loading analytics…
        </p>
      ) : null}

      {loadError ? (
        <p className="auth-error" role="alert">
          {loadError}
        </p>
      ) : null}

      {!summaryQuery.isPending && !loadError && summary ? (
        summary.overall_reply_rate === null ? (
          <p className="discovery-muted" role="status">
            No sent emails logged yet. Mark emails as sent from Search or
            History to start measuring reply rate.
          </p>
        ) : (
          <>
            <section
              className="analytics-overall"
              aria-labelledby="overall-reply-rate-heading"
            >
              <h2
                id="overall-reply-rate-heading"
                className="analytics-breakdown-heading"
              >
                Overall reply rate
              </h2>
              <p className="analytics-overall-stat">
                {summary.total_replied}/{summary.total_sent} replied (
                {formatOverallRate(summary.overall_reply_rate)})
                <span className="analytics-n">
                  {' '}
                  (n={summary.total_sent})
                </span>
              </p>
            </section>

            <AnalyticsBreakdownList
              heading="By contact confidence tier"
              headingId="by-confidence-tier-heading"
              rows={summary.by_confidence_tier.map((row) => ({
                kind: 'tier' as const,
                row,
              }))}
              emptyMessage="No sent emails in any confidence tier yet."
            />

            <AnalyticsBreakdownList
              heading="By email eval score"
              headingId="by-eval-score-heading"
              rows={summary.by_eval_score_bucket.map((row) => ({
                kind: 'eval' as const,
                row,
              }))}
              emptyMessage="No sent emails in any eval-score bucket yet."
            />
          </>
        )
      ) : null}
    </main>
  )
}
