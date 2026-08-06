import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../lib/apiClient'
import { createOutcome } from '../lib/outcomeApi'
import type { OutcomeEventType } from '../lib/outcomeTypes'
import { OUTCOMES_QUERY_KEY } from '../lib/queryKeys'

type Props = {
  generatedEmailId: number
}

const EVENT_OPTIONS: { value: OutcomeEventType; label: string }[] = [
  { value: 'sent', label: 'Sent' },
  { value: 'no_response', label: 'No response' },
  { value: 'replied', label: 'Replied' },
  { value: 'interview', label: 'Interview' },
]

/**
 * Log any OutcomeEventType against a past email (Slice 2b).
 * Reuses createOutcome — does not hardcode "sent" the way FRAME 6 does.
 */
export function LogOutcomeForm({ generatedEmailId }: Props) {
  const queryClient = useQueryClient()
  const [eventType, setEventType] = useState<OutcomeEventType>('sent')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      createOutcome({
        generated_email_id: generatedEmailId,
        event_type: eventType,
      }),
    onSuccess: () => {
      setError(null)
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

  return (
    <form
      className="log-outcome-form"
      aria-label="Log an outcome"
      onSubmit={(e) => {
        e.preventDefault()
        setError(null)
        mutation.mutate()
      }}
    >
      <label>
        Event type
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value as OutcomeEventType)}
          disabled={mutation.isPending}
        >
          {EVENT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Logging…' : error ? 'Retry' : 'Log outcome'}
      </button>
      {error ? (
        <p className="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  )
}
