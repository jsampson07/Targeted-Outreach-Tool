import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import {
  createJobDescription,
  extractJobDescription,
} from '../lib/documentApi'
import type { JDExtraction, JobDescriptionOut } from '../lib/documentTypes'

type Props = {
  companyId: number
  companyName: string
  initialJobDescription: JobDescriptionOut | null
  onReady: (jd: JobDescriptionOut) => void
  onContinue: () => void
}

function ExtractionSummary({ data }: { data: JDExtraction }) {
  return (
    <div className="extraction-summary">
      <h2 className="discovery-subhead">Extracted job description</h2>

      <div className="extraction-block">
        <h3>Required skills</h3>
        {data.required_skills.length > 0 ? (
          <ul className="extraction-list">
            {data.required_skills.map((skill) => (
              <li key={skill}>{skill}</li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No required skills extracted.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Responsibilities</h3>
        {data.responsibilities.length > 0 ? (
          <ul className="extraction-list">
            {data.responsibilities.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No responsibilities extracted.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Seniority level</h3>
        <p>{data.seniority_level ?? '—'}</p>
      </div>
    </div>
  )
}

/**
 * FRAME 5 UI: paste JD → create → extract. company_id comes from the discovered
 * contact (Frame 3), not re-entered here.
 */
export function JobDescriptionStep({
  companyId,
  companyName,
  initialJobDescription,
  onReady,
  onContinue,
}: Props) {
  const [jobDescription, setJobDescription] = useState<JobDescriptionOut | null>(
    initialJobDescription,
  )
  const [roleTitle, setRoleTitle] = useState(
    initialJobDescription?.role_title ?? '',
  )
  const [rawText, setRawText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async (payload: {
      raw_text: string
      company_id: number
      role_title: string
    }) => {
      const created = await createJobDescription(payload)
      return extractJobDescription(created.id)
    },
    onSuccess: (extracted) => {
      setError(null)
      setJobDescription(extracted)
      onReady(extracted)
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.user_message)
      } else {
        setError('Something went wrong. Please try again.')
      }
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const role_title = roleTitle.trim()
    const raw_text = rawText.trim()
    if (!role_title || !raw_text) return
    setError(null)
    mutation.mutate({ raw_text, company_id: companyId, role_title })
  }

  if (jobDescription?.extracted_data) {
    return (
      <section aria-label="JD extraction result">
        <p className="discovery-confirm" role="status">
          Job description for {companyName}
          {jobDescription.role_title
            ? ` — ${jobDescription.role_title}`
            : ''}
        </p>
        <ExtractionSummary data={jobDescription.extracted_data} />
        <button type="button" onClick={onContinue}>
          Continue to generate email
        </button>
      </section>
    )
  }

  return (
    <section aria-label="JD paste form">
      <p className="discovery-lead">
        Paste the job posting for {companyName}. We&apos;ll extract required
        skills, responsibilities, and seniority.
      </p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Role title
          <input
            type="text"
            name="jdRoleTitle"
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
            placeholder="e.g. Software Engineer"
            required
          />
        </label>
        <label>
          Job description
          <textarea
            name="jdRawText"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            rows={10}
            required
          />
        </label>
        <button type="submit" disabled={mutation.isPending}>
          {mutation.isPending
            ? 'Saving and extracting…'
            : 'Save and extract'}
        </button>
      </form>
      {error ? (
        <p className="auth-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}
