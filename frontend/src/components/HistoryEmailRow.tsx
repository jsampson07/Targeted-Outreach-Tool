import { useState } from 'react'

import type { GeneratedEmailListOut } from '../lib/generatedEmailTypes'
import type { OutcomeOut } from '../lib/outcomeTypes'
import { HistoryEmailDetail } from './HistoryEmailDetail'

type Props = {
  email: GeneratedEmailListOut
  outcomes: OutcomeOut[]
}

function formatCreatedAt(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString()
}

function contactLine(email: GeneratedEmailListOut): string {
  const name = email.contact_name?.trim() || 'Unknown contact'
  const title = email.contact_title?.trim()
  return title ? `${name} · ${title}` : name
}

/**
 * One history list row. Accordion via &lt;details&gt; — same disclosure pattern
 * as match_data / confidence_breakdown elsewhere. Detail fetch only when open.
 */
export function HistoryEmailRow({ email, outcomes }: Props) {
  const [open, setOpen] = useState(false)
  const isLogged = outcomes.length > 0

  return (
    <details
      className="history-email-row"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="history-email-summary">
        <span className="history-email-subject">{email.subject}</span>
        <span className="history-email-meta">
          <span>{contactLine(email)}</span>
          <span>{email.company_name}</span>
          <span>Eval {email.eval_score.toFixed(1)}</span>
          <span
            className={
              email.gate_passed
                ? 'history-gate history-gate-passed'
                : 'history-gate history-gate-flagged'
            }
          >
            {email.gate_passed ? 'Gate pass' : 'Gate fail'}
          </span>
          <span className="history-email-date">
            {formatCreatedAt(email.created_at)}
          </span>
          <span
            className={
              isLogged
                ? 'history-logged-badge history-logged-yes'
                : 'history-logged-badge history-logged-no'
            }
          >
            {isLogged ? 'Logged' : 'Not logged'}
          </span>
        </span>
      </summary>
      <HistoryEmailDetail
        emailId={email.id}
        outcomes={outcomes}
        enabled={open}
      />
    </details>
  )
}
