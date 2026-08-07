import { useEffect, useState } from 'react'

import type { GeneratedEmailListOut } from '../lib/generatedEmailTypes'
import type { OutcomeOut } from '../lib/outcomeTypes'
import { HistoryEmailDetail } from './HistoryEmailDetail'

type Props = {
  email: GeneratedEmailListOut
  outcomes: OutcomeOut[]
  /** Controlled by HistoryPage — only one row expanded at a time. */
  expanded: boolean
  onToggle: () => void
}

/** Keep mounted briefly after collapse so the CSS height transition can run. */
const COLLAPSE_UNMOUNT_MS = 280

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
 * One history list row. Expand/collapse is controlled by the parent via a
 * single page-level expandedId (accordion: at most one open). Detail fetch
 * only when expanded. Panel stays mounted briefly on collapse for the CSS
 * transition, then unmounts.
 */
export function HistoryEmailRow({
  email,
  outcomes,
  expanded,
  onToggle,
}: Props) {
  const isLogged = outcomes.length > 0
  /** Content stays mounted during the collapse CSS transition, then unmounts. */
  const [detailMounted, setDetailMounted] = useState(expanded)
  /** Visual open state lags one frame on expand so grid-template-rows can animate. */
  const [animOpen, setAnimOpen] = useState(false)

  useEffect(() => {
    if (expanded) {
      setDetailMounted(true)
      const frameId = window.requestAnimationFrame(() => {
        setAnimOpen(true)
      })
      return () => window.cancelAnimationFrame(frameId)
    }
    setAnimOpen(false)
    const timeoutId = window.setTimeout(() => {
      setDetailMounted(false)
    }, COLLAPSE_UNMOUNT_MS)
    return () => window.clearTimeout(timeoutId)
  }, [expanded])

  return (
    <div
      className={
        expanded
          ? 'history-email-row history-email-row-expanded'
          : 'history-email-row'
      }
    >
      <button
        type="button"
        className="history-email-summary"
        aria-expanded={expanded}
        onClick={onToggle}
      >
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
      </button>
      <div
        className={
          animOpen
            ? 'history-email-expand is-expanded'
            : 'history-email-expand'
        }
        aria-hidden={!expanded}
        {...(!expanded ? { inert: true } : {})}
      >
        <div className="history-email-expand-inner">
          {detailMounted ? (
            <HistoryEmailDetail
              emailId={email.id}
              outcomes={outcomes}
              enabled={expanded}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
