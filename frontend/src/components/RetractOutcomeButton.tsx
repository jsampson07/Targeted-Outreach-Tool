import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../lib/apiClient'
import { retractOutcome } from '../lib/outcomeApi'
import type { OutcomeEventType } from '../lib/outcomeTypes'
import { OUTCOMES_QUERY_KEY } from '../lib/queryKeys'

type Props = {
  outcomeId: number
  eventType: OutcomeEventType
  /**
   * True when this email has other non-voided outcomes besides this row
   * (derived from the page-level in-memory group — no extra fetch).
   */
  hasOtherNonVoidedOutcomes: boolean
}

/**
 * Inline two-click retract confirm (Retract → Confirm / Cancel).
 * Avoids native window.confirm(); matches the app's non-dialog pattern.
 *
 * Retracting a Sent row that has dependent outcomes shows cascade copy
 * before Confirm — backend voids those siblings in the same transaction.
 */
export function RetractOutcomeButton({
  outcomeId,
  eventType,
  hasOtherNonVoidedOutcomes,
}: Props) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => retractOutcome(outcomeId),
    onSuccess: () => {
      setError(null)
      setConfirming(false)
      // Full outcomes list refetch — picks up cascade-voided siblings too.
      void queryClient.invalidateQueries({ queryKey: OUTCOMES_QUERY_KEY })
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.user_message)
      } else {
        setError('Something went wrong. Please try again.')
      }
    },
  })

  const showCascadeCopy =
    eventType === 'sent' && hasOtherNonVoidedOutcomes

  if (confirming) {
    return (
      <span className="retract-confirm">
        {showCascadeCopy ? (
          <span className="retract-confirm-copy">
            Retracting &apos;Sent&apos; will also retract all other logged
            outcomes for this email. Retract?
          </span>
        ) : null}
        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => {
            setError(null)
            mutation.mutate()
          }}
        >
          {mutation.isPending ? 'Retracting…' : 'Confirm'}
        </button>
        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => {
            setConfirming(false)
            setError(null)
          }}
        >
          Cancel
        </button>
        {error ? (
          <span className="auth-error" role="alert">
            {error}
          </span>
        ) : null}
      </span>
    )
  }

  return (
    <span className="retract-control">
      <button type="button" onClick={() => setConfirming(true)}>
        Retract
      </button>
      {error ? (
        <span className="auth-error" role="alert">
          {error}
        </span>
      ) : null}
    </span>
  )
}
