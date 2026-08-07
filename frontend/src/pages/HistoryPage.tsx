import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { AppHeader } from '../components/AppHeader'
import { HistoryEmailRow } from '../components/HistoryEmailRow'
import {
  HistoryFilter,
  type HistoryFilterValue,
} from '../components/HistoryFilter'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../lib/apiClient'
import { listGeneratedEmails } from '../lib/generatedEmailApi'
import { groupOutcomesByEmailId } from '../lib/groupOutcomesByEmailId'
import { listOutcomes } from '../lib/outcomeApi'
import {
  GENERATED_EMAILS_QUERY_KEY,
  OUTCOMES_QUERY_KEY,
} from '../lib/queryKeys'

/**
 * /history — browse past generated emails, see logged outcomes, log any event
 * type, retract mistaken logs.
 *
 * Deliberately does NOT use sessionStorage (contrast with /'s discoveryFlow):
 * GET /generated-emails and GET /outcomes are free, idempotent reads; refetch
 * on mount/refresh is correct. sessionStorage on / exists to avoid re-spending
 * LLM/provider credits — that concern does not apply here.
 */
export function HistoryPage() {
  const { logout } = useAuth()
  const [filter, setFilter] = useState<HistoryFilterValue>('logged')
  /** At most one expanded row; null = all collapsed. Reset on filter change. */
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const emailsQuery = useQuery({
    queryKey: GENERATED_EMAILS_QUERY_KEY,
    queryFn: listGeneratedEmails,
  })

  const outcomesQuery = useQuery({
    queryKey: OUTCOMES_QUERY_KEY,
    queryFn: () => listOutcomes(),
  })

  const outcomesByEmail = useMemo(
    () => groupOutcomesByEmailId(outcomesQuery.data ?? []),
    [outcomesQuery.data],
  )

  const filteredEmails = useMemo(() => {
    const emails = emailsQuery.data ?? []
    if (filter === 'all') return emails
    if (filter === 'logged') {
      return emails.filter((email) => (outcomesByEmail.get(email.id)?.length ?? 0) > 0)
    }
    return emails.filter((email) => (outcomesByEmail.get(email.id)?.length ?? 0) === 0)
  }, [emailsQuery.data, filter, outcomesByEmail])

  function handleFilterChange(value: HistoryFilterValue) {
    setFilter(value)
    setExpandedId(null)
  }

  function handleRowToggle(emailId: number) {
    setExpandedId((current) => (current === emailId ? null : emailId))
  }

  const loading = emailsQuery.isPending || outcomesQuery.isPending
  const loadError =
    emailsQuery.error instanceof ApiError
      ? emailsQuery.error.user_message
      : outcomesQuery.error instanceof ApiError
        ? outcomesQuery.error.user_message
        : emailsQuery.isError || outcomesQuery.isError
          ? 'Something went wrong. Please try again.'
          : null

  return (
    <main className="home-page discovery-page history-page">
      <AppHeader
        actions={
          <button type="button" onClick={() => void logout()}>
            Log out
          </button>
        }
      />

      <h1 className="history-heading">Outreach history</h1>
      <p className="discovery-lead">
        Past generated emails and their outcome logs. Filter locally — lists
        reload from the server on each visit (no session cache).
      </p>

      <HistoryFilter value={filter} onChange={handleFilterChange} />

      {loading ? (
        <p className="discovery-muted" role="status">
          Loading history…
        </p>
      ) : null}

      {loadError ? (
        <p className="auth-error" role="alert">
          {loadError}
        </p>
      ) : null}

      {!loading && !loadError ? (
        filteredEmails.length === 0 ? (
          <p className="discovery-muted" role="status">
            {filter === 'logged'
              ? 'No emails with logged outcomes yet.'
              : filter === 'unlogged'
                ? 'Every email already has at least one outcome.'
                : 'No generated emails yet.'}
          </p>
        ) : (
          <ul className="history-email-list">
            {filteredEmails.map((email) => (
              <li key={email.id}>
                <HistoryEmailRow
                  email={email}
                  outcomes={outcomesByEmail.get(email.id) ?? []}
                  expanded={expandedId === email.id}
                  onToggle={() => handleRowToggle(email.id)}
                />
              </li>
            ))}
          </ul>
        )
      ) : null}
    </main>
  )
}
