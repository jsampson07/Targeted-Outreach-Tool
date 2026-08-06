import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../lib/apiClient'
import { retractOutcome } from '../lib/outcomeApi'
import { OUTCOMES_QUERY_KEY } from '../lib/queryKeys'

type Props = {
  outcomeId: number
}

/**
 * Inline two-click retract confirm (Retract → Confirm / Cancel).
 * Avoids native window.confirm(); matches the app's non-dialog pattern.
 */
export function RetractOutcomeButton({ outcomeId }: Props) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => retractOutcome(outcomeId),
    onSuccess: () => {
      setError(null)
      setConfirming(false)
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

  if (confirming) {
    return (
      <span className="retract-confirm">
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
