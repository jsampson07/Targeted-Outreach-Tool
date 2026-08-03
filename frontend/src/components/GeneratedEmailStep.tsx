import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../lib/apiClient'
import { generateEmail } from '../lib/generatedEmailApi'
import type {
  EvalDimensions,
  GeneratedEmailOut,
  MatchData,
} from '../lib/generatedEmailTypes'

type Props = {
  contactId: number
  resumeId: number
  jobDescriptionId: number
  initialGeneratedEmail: GeneratedEmailOut | null
  onReady: (email: GeneratedEmailOut) => void
}

const DIMENSION_LABELS: Record<keyof EvalDimensions, string> = {
  role_company_specificity: 'Role / company specificity',
  relevance_alignment: 'Relevance alignment',
  tone_professionalism: 'Tone / professionalism',
  conciseness: 'Conciseness',
  clear_cta: 'Clear CTA',
}

function formatPasteReady(email: GeneratedEmailOut): string {
  return `Subject: ${email.subject}\n\n${email.body}`
}

function MatchDataDetails({ matchData }: { matchData: MatchData }) {
  return (
    <details className="match-data-details">
      <summary>Match details</summary>

      <div className="extraction-block">
        <h3>Skill matches</h3>
        {matchData.skill_matches.length > 0 ? (
          <ul className="extraction-list">
            {matchData.skill_matches.map((item, index) => (
              <li key={`${item.jd_requirement}-${index}`}>
                {item.matched ? 'Matched' : 'Unmatched'}: {item.jd_requirement}
                {item.resume_evidence
                  ? ` — ${item.resume_evidence}`
                  : ''}
              </li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No skill matches recorded.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Experience alignment</h3>
        {matchData.experience_alignment.length > 0 ? (
          <ul className="extraction-list">
            {matchData.experience_alignment.map((item, index) => (
              <li key={`${item.jd_responsibility}-${index}`}>
                [{item.strength}] {item.jd_responsibility}
                {item.resume_evidence
                  ? ` — ${item.resume_evidence}`
                  : ''}
              </li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No experience alignment recorded.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Unmatched JD requirements</h3>
        {matchData.unmatched_jd_requirements.length > 0 ? (
          <ul className="extraction-list">
            {matchData.unmatched_jd_requirements.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">None.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Notable resume strengths</h3>
        {matchData.notable_resume_strengths.length > 0 ? (
          <ul className="extraction-list">
            {matchData.notable_resume_strengths.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">None listed.</p>
        )}
      </div>
    </details>
  )
}

function EmailResult({ email }: { email: GeneratedEmailOut }) {
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>(
    'idle',
  )

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(formatPasteReady(email))
      setCopyStatus('copied')
    } catch {
      setCopyStatus('failed')
    }
  }

  const { dimensions, gates } = email.eval_breakdown

  return (
    <section aria-label="Generated email result">
      <p className="discovery-confirm" role="status">
        Generated outreach email
      </p>

      <div className="email-meta">
        <p className="eval-score">
          Eval score: {email.eval_score.toFixed(1)}
        </p>
        {email.gate_passed ? (
          <p className="gate-status gate-passed" role="status">
            Cleared hard gates
          </p>
        ) : (
          <p className="gate-status gate-flagged" role="status">
            Flagged — did not clear hard gates
          </p>
        )}
      </div>

      <div className="email-draft">
        <h2 className="discovery-subhead">Subject</h2>
        <p className="email-subject">{email.subject}</p>
        <h2 className="discovery-subhead">Body</h2>
        <pre className="email-body">{email.body}</pre>
      </div>

      <button type="button" onClick={() => void handleCopy()}>
        Copy subject and body
      </button>
      {copyStatus === 'copied' ? (
        <p className="discovery-muted" role="status">
          Copied to clipboard.
        </p>
      ) : null}
      {copyStatus === 'failed' ? (
        <p className="auth-error" role="alert">
          Could not copy to clipboard. Please copy manually.
        </p>
      ) : null}

      <div className="eval-breakdown">
        <h2 className="discovery-subhead">Eval dimensions</h2>
        <dl className="eval-dimensions">
          {(Object.keys(DIMENSION_LABELS) as (keyof EvalDimensions)[]).map(
            (key) => (
              <div key={key}>
                <dt>{DIMENSION_LABELS[key]}</dt>
                <dd>{dimensions[key]} / 5</dd>
              </div>
            ),
          )}
        </dl>

        <h2 className="discovery-subhead">Hard gates</h2>
        <dl className="eval-gates">
          <div>
            <dt>No unsupported claims</dt>
            <dd>{gates.no_unsupported_claims ? 'Pass' : 'Fail'}</dd>
          </div>
          <div>
            <dt>Correct contact name used</dt>
            <dd>{gates.correct_contact_name_used ? 'Pass' : 'Fail'}</dd>
          </div>
        </dl>
      </div>

      <div className="match-summary-block">
        <h2 className="discovery-subhead">Match summary</h2>
        <p className="match-summary">{email.match_data.overall_match_summary}</p>
        <MatchDataDetails matchData={email.match_data} />
      </div>
    </section>
  )
}

/**
 * FRAME 6 UI: explicit Generate Email mutation → display GeneratedEmailOut.
 * Single-shot: once a result exists (live or rehydrated), no Generate button.
 */
export function GeneratedEmailStep({
  contactId,
  resumeId,
  jobDescriptionId,
  initialGeneratedEmail,
  onReady,
}: Props) {
  const [generatedEmail, setGeneratedEmail] =
    useState<GeneratedEmailOut | null>(initialGeneratedEmail)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      generateEmail({
        contact_id: contactId,
        resume_id: resumeId,
        job_description_id: jobDescriptionId,
      }),
    onSuccess: (email) => {
      setError(null)
      setGeneratedEmail(email)
      onReady(email)
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.user_message)
      } else {
        setError('Something went wrong. Please try again.')
      }
    },
  })

  if (generatedEmail) {
    return <EmailResult email={generatedEmail} />
  }

  return (
    <section aria-label="Generate email">
      <p className="discovery-lead">
        Resume, job description, and contact are ready. Generate a grounded
        outreach email — this spends LLM credits (generation + eval).
      </p>
      <button
        type="button"
        className="primary-action"
        disabled={mutation.isPending}
        onClick={() => {
          setError(null)
          mutation.mutate()
        }}
      >
        {mutation.isPending
          ? 'Generating…'
          : error
            ? 'Retry'
            : 'Generate Email'}
      </button>
      {error ? (
        <p className="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}
