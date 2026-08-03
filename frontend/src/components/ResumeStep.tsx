import { useState, type FormEvent } from 'react'

import type { UseResumeForGenerationResult } from '../hooks/useResumeForGeneration'
import type { ResumeExtraction } from '../lib/documentTypes'

type Props = {
  resumeForGeneration: UseResumeForGenerationResult
  onContinue: () => void
}

function ExtractionSummary({ data }: { data: ResumeExtraction }) {
  return (
    <div className="extraction-summary">
      <h2 className="discovery-subhead">Extracted resume</h2>

      <div className="extraction-block">
        <h3>Skills</h3>
        {data.skills.length > 0 ? (
          <ul className="extraction-list">
            {data.skills.map((skill) => (
              <li key={skill}>{skill}</li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No skills extracted.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Experience</h3>
        {data.experience.length > 0 ? (
          <ul className="experience-list">
            {data.experience.map((entry, index) => (
              <li key={`${entry.company}-${entry.title}-${index}`}>
                <p className="experience-heading">
                  {entry.title} · {entry.company}
                </p>
                <p className="discovery-muted">
                  {entry.start_date}
                  {' – '}
                  {entry.end_date ?? 'present'}
                </p>
                {entry.bullet_points.length > 0 ? (
                  <ul className="extraction-list">
                    {entry.bullet_points.map((bullet, i) => (
                      <li key={i}>{bullet}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No experience extracted.</p>
        )}
      </div>

      <div className="extraction-block">
        <h3>Education</h3>
        {data.education.length > 0 ? (
          <ul className="extraction-list">
            {data.education.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="discovery-muted">No education extracted.</p>
        )}
      </div>
    </div>
  )
}

/**
 * FRAME 4 UI: file picker → upload+extract via useResumeForGeneration.
 * Does not decide how resume_id is obtained — that lives in the hook.
 */
export function ResumeStep({ resumeForGeneration, onContinue }: Props) {
  const { resume, isPending, error, obtainFromUpload } = resumeForGeneration
  const [file, setFile] = useState<File | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    obtainFromUpload(file)
  }

  if (resume?.extracted_data) {
    return (
      <section aria-label="Resume extraction">
        <ExtractionSummary data={resume.extracted_data} />
        <button type="button" onClick={onContinue}>
          Continue to job description
        </button>
      </section>
    )
  }

  return (
    <section aria-label="Resume upload">
      <p className="discovery-lead">
        Upload your resume (PDF or DOCX, max 2MB). We&apos;ll extract skills,
        experience, and education for the outreach draft.
      </p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Resume file
          <input
            type="file"
            name="resumeFile"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={isPending || !file}>
          {isPending ? 'Uploading and extracting…' : 'Upload and extract'}
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
