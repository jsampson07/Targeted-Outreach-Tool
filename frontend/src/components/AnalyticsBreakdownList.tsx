import type {
  ConfidenceTierBreakdown,
  EvalScoreBucketBreakdown,
} from '../lib/analyticsTypes'

type BreakdownRow =
  | { kind: 'tier'; row: ConfidenceTierBreakdown }
  | { kind: 'eval'; row: EvalScoreBucketBreakdown }

function formatRate(replyRate: number): string {
  return `${Math.round(replyRate * 100)}%`
}

function formatLabel(item: BreakdownRow): string {
  if (item.kind === 'tier') {
    return item.row.tier.replaceAll('_', ' ')
  }
  return item.row.bucket
}

type AnalyticsBreakdownListProps = {
  heading: string
  headingId: string
  rows: BreakdownRow[]
  emptyMessage: string
}

/**
 * Simple rate + n= list for one analytics breakdown. Buckets with sent=0 are
 * already omitted by the API — this only renders what it receives.
 */
export function AnalyticsBreakdownList({
  heading,
  headingId,
  rows,
  emptyMessage,
}: AnalyticsBreakdownListProps) {
  return (
    <section className="analytics-breakdown" aria-labelledby={headingId}>
      <h2 id={headingId} className="analytics-breakdown-heading">
        {heading}
      </h2>
      {rows.length === 0 ? (
        <p className="discovery-muted">{emptyMessage}</p>
      ) : (
        <ul className="analytics-breakdown-list">
          {rows.map((item) => {
            const key =
              item.kind === 'tier' ? item.row.tier : item.row.bucket
            const { sent, replied, reply_rate: replyRate } = item.row
            return (
              <li key={key} className="analytics-breakdown-row">
                <span className="analytics-breakdown-label">
                  {formatLabel(item)}
                </span>
                <span className="analytics-breakdown-stat">
                  {formatRate(replyRate)}{' '}
                  <span className="analytics-n">
                    (n={sent}; {replied}/{sent} replied)
                  </span>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
