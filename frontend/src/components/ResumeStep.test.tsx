import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { UseResumeForGenerationResult } from '../hooks/useResumeForGeneration'
import type { ResumeExtraction, ResumeOut } from '../lib/documentTypes'
import { ResumeStep } from './ResumeStep'

function resumeOut(extracted: ResumeExtraction): ResumeOut {
  return {
    id: 1,
    user_id: 1,
    raw_text: 'resume text',
    extracted_data: extracted,
    created_at: '2026-08-03T00:00:00Z',
  }
}

function stubResumeForGeneration(
  extracted: ResumeExtraction,
): UseResumeForGenerationResult {
  return {
    resume: resumeOut(extracted),
    resumeId: 1,
    isPending: false,
    error: null,
    obtainFromUpload: vi.fn(),
    reset: vi.fn(),
  }
}

function renderExtraction(extracted: ResumeExtraction) {
  return render(
    <ResumeStep
      resumeForGeneration={stubResumeForGeneration(extracted)}
      onContinue={vi.fn()}
    />,
  )
}

const emptyLists: Pick<
  ResumeExtraction,
  'skills' | 'experience' | 'education' | 'projects'
> = {
  skills: [],
  experience: [],
  education: [],
  projects: [],
}

describe('ResumeStep extraction summary', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders candidate_name when present', () => {
    renderExtraction({
      ...emptyLists,
      candidate_name: 'Jane Doe',
    })

    expect(screen.getByText('Candidate name')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(
      screen.queryByText(
        'No candidate name extracted — emails will sign off without a name.',
      ),
    ).not.toBeInTheDocument()
  })

  it('renders muted fallback when candidate_name is null', () => {
    renderExtraction({
      ...emptyLists,
      candidate_name: null,
    })

    expect(
      screen.getByText(
        'No candidate name extracted — emails will sign off without a name.',
      ),
    ).toBeInTheDocument()
  })

  it('renders project name, description, technologies, and bullet_points', () => {
    renderExtraction({
      ...emptyLists,
      candidate_name: 'Jane Doe',
      projects: [
        {
          name: 'Outreach Tool',
          description: 'Personal cold-email helper',
          technologies: ['React', 'Postgres'],
          bullet_points: ['Structured LLM extraction'],
        },
      ],
    })

    expect(screen.getByText('Outreach Tool')).toBeInTheDocument()
    expect(screen.getByText('Personal cold-email helper')).toBeInTheDocument()
    expect(screen.getByText('React, Postgres')).toBeInTheDocument()
    expect(screen.getByText('Structured LLM extraction')).toBeInTheDocument()
  })

  it('omits description, technologies, and bullets when a project entry leaves them empty', () => {
    renderExtraction({
      ...emptyLists,
      candidate_name: 'Jane Doe',
      projects: [
        {
          name: 'Sparse Project',
          description: null,
          technologies: [],
          bullet_points: [],
        },
      ],
    })

    expect(screen.getByText('Sparse Project')).toBeInTheDocument()
    expect(screen.queryByText('No projects extracted.')).not.toBeInTheDocument()

    const projectItem = screen.getByText('Sparse Project').closest('li')
    expect(projectItem).not.toBeNull()
    // Only the name heading — no muted description/tech <p>, no bullet <ul>.
    expect(projectItem!.querySelectorAll('p.discovery-muted')).toHaveLength(0)
    expect(projectItem!.querySelector('ul')).toBeNull()
  })

  it('renders empty-projects fallback', () => {
    renderExtraction({
      ...emptyLists,
      candidate_name: 'Jane Doe',
      projects: [],
    })

    expect(screen.getByText('No projects extracted.')).toBeInTheDocument()
  })
})
