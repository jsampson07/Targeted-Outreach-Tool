import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '../lib/apiClient'
import { DISCOVERY_FLOW_KEY } from '../lib/discoverySession'
import type { ContactDiscoveryResponse } from '../lib/discoveryTypes'
import { HomePage } from './HomePage'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function seedAuth() {
  localStorage.setItem(ACCESS_TOKEN_KEY, 'access-token')
  localStorage.setItem(REFRESH_TOKEN_KEY, 'refresh-token')
}

function renderHome() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <HomePage />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

const sampleContact: ContactDiscoveryResponse = {
  contact: {
    id: 1,
    company_id: 10,
    name: 'Alex Recruiter',
    title: 'Technical Recruiter',
    email: 'alex@acme.com',
    best_verification_tier: 'verified',
    confidence_score: 0.82,
    confidence_breakdown: {
      verification_tier_score: 1,
      cross_provider_corroboration: false,
      employment_currency_signal: 'unknown',
      domain_check_passed: true,
      name_collision_detected: false,
    },
  },
  fallback_reason: 'No dedicated recruiter found; showing hiring manager instead.',
  tier_used: 'hiring_manager',
}

const notFoundResult: ContactDiscoveryResponse = {
  contact: null,
  fallback_reason: null,
  tier_used: null,
}

describe('HomePage discovery flow', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    seedAuth()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    cleanup()
    localStorage.clear()
    sessionStorage.clear()
    vi.unstubAllGlobals()
  })

  it('search success shows candidates and does not auto-select a single match', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        candidates: [{ name: 'Acme Inc', domain: 'acme.com' }],
      }),
    )

    renderHome()

    await user.type(screen.getByLabelText(/company name/i), 'Acme')
    await user.click(screen.getByRole('button', { name: /^search$/i }))

    expect(
      await screen.findByRole('button', { name: /acme inc/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('acme.com')).toBeInTheDocument()
    // Still FRAME 1 — role title / confirmation must not appear yet.
    expect(
      screen.queryByText(/searching contacts at/i),
    ).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/companies/search',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('selecting a candidate locks the company and advances to FRAME 2', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        candidates: [
          { name: 'Acme Inc', domain: 'acme.com' },
          { name: 'Acme Labs', domain: 'acmelabs.io' },
        ],
      }),
    )

    renderHome()

    await user.type(screen.getByLabelText(/company name/i), 'Acme')
    await user.click(screen.getByRole('button', { name: /^search$/i }))
    await user.click(await screen.findByRole('button', { name: /acme labs/i }))

    expect(
      screen.getByText(/searching contacts at acme labs \(acmelabs\.io\)/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/role title/i)).toBeInTheDocument()
    expect(sessionStorage.getItem(DISCOVERY_FLOW_KEY)).toContain('acmelabs.io')
    expect(
      JSON.parse(sessionStorage.getItem(DISCOVERY_FLOW_KEY)!).discoveryResult,
    ).toBeNull()
  })

  it('zero candidates triggers the manual domain fallback', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ candidates: [] }))

    renderHome()

    await user.type(screen.getByLabelText(/company name/i), 'Tiny Startup')
    await user.click(screen.getByRole('button', { name: /^search$/i }))

    expect(
      await screen.findByText(/haven't found what you're looking for/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/company domain/i)).toBeInTheDocument()
  })

  it('search error triggers the same manual domain fallback', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(
        {
          user_message: 'Company lookup is temporarily unavailable.',
          error_code: 'ProviderUnavailableError',
        },
        502,
      ),
    )

    renderHome()

    await user.type(screen.getByLabelText(/company name/i), 'Acme')
    await user.click(screen.getByRole('button', { name: /^search$/i }))

    expect(
      await screen.findByText(/haven't found what you're looking for/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/company domain/i)).toBeInTheDocument()
    expect(
      screen.getByText(/company lookup is temporarily unavailable/i),
    ).toBeInTheDocument()
  })

  it('manual fallback confirm locks company and advances to FRAME 2', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ candidates: [] }))

    renderHome()

    await user.type(screen.getByLabelText(/company name/i), 'Tiny Co')
    await user.click(screen.getByRole('button', { name: /^search$/i }))
    await screen.findByText(/haven't found what you're looking for/i)

    const domainInput = screen.getByLabelText(/company domain/i)
    await user.type(domainInput, 'tiny.co')
    await user.click(
      screen.getByRole('button', { name: /use this company/i }),
    )

    expect(
      screen.getByText(/searching contacts at tiny co \(tiny\.co\)/i),
    ).toBeInTheDocument()
    expect(
      JSON.parse(sessionStorage.getItem(DISCOVERY_FLOW_KEY)!).company,
    ).toEqual({ name: 'Tiny Co', domain: 'tiny.co' })
  })

  it('discover success with a contact renders FRAME 3 details and fallback reason', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: null,
      }),
    )
    vi.mocked(fetch).mockResolvedValue(jsonResponse(sampleContact))

    renderHome()

    await user.type(screen.getByLabelText(/role title/i), 'Engineer')
    await user.click(screen.getByRole('button', { name: /find contact/i }))

    expect(await screen.findByText('Alex Recruiter')).toBeInTheDocument()
    expect(screen.getByText('alex@acme.com')).toBeInTheDocument()
    expect(screen.getByText('verified')).toBeInTheDocument()
    expect(screen.getByText('0.82')).toBeInTheDocument()
    expect(
      screen.getByText(/no dedicated recruiter found/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue to resume/i }),
    ).toBeInTheDocument()

    const details = screen.getByText('Confidence breakdown').closest('details')
    expect(details).not.toBeNull()
    expect(details).not.toHaveAttribute('open')
    await user.click(screen.getByText('Confidence breakdown'))
    expect(
      within(details as HTMLElement).getByText('Verification tier score'),
    ).toBeInTheDocument()
    expect(
      within(details as HTMLElement).getByText('Employment currency signal'),
    ).toBeInTheDocument()

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/contacts/discover',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(
      JSON.parse(sessionStorage.getItem(DISCOVERY_FLOW_KEY)!).discoveryResult
        .contact.email,
    ).toBe('alex@acme.com')
  })

  it('discover success with contact null renders calm not-found FRAME 3', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: null,
      }),
    )
    vi.mocked(fetch).mockResolvedValue(jsonResponse(notFoundResult))

    renderHome()

    await user.type(screen.getByLabelText(/role title/i), 'Engineer')
    await user.click(screen.getByRole('button', { name: /find contact/i }))

    expect(
      await screen.findByText(/no contact could be found for this company/i),
    ).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/try a different company/i),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /continue to resume/i }),
    ).not.toBeInTheDocument()
    expect(
      JSON.parse(sessionStorage.getItem(DISCOVERY_FLOW_KEY)!).discoveryResult
        .contact,
    ).toBeNull()
  })

  it('discover mutation error surfaces user_message', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: null,
      }),
    )
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(
        {
          user_message: 'Contact discovery is temporarily unavailable.',
          error_code: 'ProviderUnavailableError',
        },
        502,
      ),
    )

    renderHome()

    await user.type(screen.getByLabelText(/role title/i), 'Engineer')
    await user.click(screen.getByRole('button', { name: /find contact/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Contact discovery is temporarily unavailable.',
    )
    expect(
      screen.queryByText(/no contact could be found/i),
    ).not.toBeInTheDocument()
  })

  it('rehydrates to FRAME 2 when sessionStorage has company only', () => {
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: null,
      }),
    )

    renderHome()

    expect(
      screen.getByText(/searching contacts at acme inc \(acme\.com\)/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/role title/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /^search$/i }),
    ).not.toBeInTheDocument()
  })

  it('rehydrates to FRAME 3 when sessionStorage has company + discoveryResult', () => {
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
      }),
    )

    renderHome()

    expect(screen.getByText('Alex Recruiter')).toBeInTheDocument()
    expect(screen.getByText('alex@acme.com')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /^search$/i }),
    ).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/role title/i)).not.toBeInTheDocument()
  })

  it('start new search clears component state and sessionStorage', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
      }),
    )

    renderHome()
    expect(screen.getByText('Alex Recruiter')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /start new search/i }),
    )

    await waitFor(() => {
      expect(sessionStorage.getItem(DISCOVERY_FLOW_KEY)).toBeNull()
    })
    expect(screen.getByRole('button', { name: /^search$/i })).toBeInTheDocument()
    expect(screen.queryByText('Alex Recruiter')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/searching contacts at/i),
    ).not.toBeInTheDocument()
  })

  it('continue from FRAME 3 advances to resume upload FRAME 4', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
        resume: null,
        jobDescription: null,
      }),
    )

    renderHome()
    await user.click(
      screen.getByRole('button', { name: /continue to resume/i }),
    )

    expect(screen.getByLabelText(/resume file/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /upload and extract/i }),
    ).toBeInTheDocument()
    expect(screen.queryByText('Alex Recruiter')).not.toBeInTheDocument()
  })

  it('rejects oversized resume client-side without calling the API', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
        resume: null,
        jobDescription: null,
      }),
    )

    renderHome()
    await user.click(
      screen.getByRole('button', { name: /continue to resume/i }),
    )

    const big = new File(['x'], 'huge.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 2 * 1024 * 1024 + 1 })
    const input = screen.getByLabelText(/resume file/i) as HTMLInputElement
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [big],
    })
    fireEvent.change(input)
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /upload and extract/i }),
      ).toBeEnabled()
    })
    await user.click(
      screen.getByRole('button', { name: /upload and extract/i }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/file too large/i)
    expect(fetch).not.toHaveBeenCalled()
  })

  it('resume upload+extract shows extraction and persists to sessionStorage', async () => {
    const user = userEvent.setup()
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
        resume: null,
        jobDescription: null,
      }),
    )

    const uploaded = {
      id: 7,
      user_id: 1,
      raw_text: 'Jane Doe Python engineer',
      extracted_data: null,
      created_at: '2026-08-03T00:00:00Z',
    }
    const extracted = {
      ...uploaded,
      extracted_data: {
        skills: ['Python', 'FastAPI'],
        experience: [
          {
            company: 'Acme',
            title: 'Engineer',
            start_date: '2022',
            end_date: null,
            bullet_points: ['Built APIs'],
          },
        ],
        education: ['BS CS'],
      },
    }

    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(uploaded, 201))
      .mockResolvedValueOnce(jsonResponse(extracted))

    renderHome()
    await user.click(
      screen.getByRole('button', { name: /continue to resume/i }),
    )

    const file = new File(['%PDF-1.4 resume'], 'resume.pdf', {
      type: 'application/pdf',
    })
    const input = screen.getByLabelText(/resume file/i) as HTMLInputElement
    Object.defineProperty(input, 'files', {
      configurable: true,
      value: [file],
    })
    fireEvent.change(input)
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /upload and extract/i }),
      ).toBeEnabled()
    })
    await user.click(
      screen.getByRole('button', { name: /upload and extract/i }),
    )

    expect(await screen.findByText('Extracted resume')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('FastAPI')).toBeInTheDocument()
    expect(screen.getByText(/Engineer · Acme/)).toBeInTheDocument()
    expect(screen.getByText('BS CS')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue to job description/i }),
    ).toBeInTheDocument()

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/resumes',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/resumes/7/extract',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(
      JSON.parse(sessionStorage.getItem(DISCOVERY_FLOW_KEY)!).resume.id,
    ).toBe(7)
  })

  it('JD create+extract shows extraction using company_id from contact', async () => {
    const user = userEvent.setup()
    const resume = {
      id: 7,
      user_id: 1,
      raw_text: 'Jane Doe',
      extracted_data: {
        skills: ['Python'],
        experience: [],
        education: [],
      },
      created_at: '2026-08-03T00:00:00Z',
    }
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
        resume,
        jobDescription: null,
      }),
    )

    const createdJd = {
      id: 3,
      user_id: 1,
      company_id: 10,
      role_title: 'Software Engineer',
      raw_text: 'Build APIs with Python',
      extracted_data: null,
      created_at: '2026-08-03T00:00:00Z',
    }
    const extractedJd = {
      ...createdJd,
      extracted_data: {
        required_skills: ['Python', 'SQL'],
        responsibilities: ['Own services'],
        seniority_level: 'mid',
      },
    }

    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(createdJd, 201))
      .mockResolvedValueOnce(jsonResponse(extractedJd))

    renderHome()

    // Rehydrate lands on resume confirmation (resume present, no JD yet).
    expect(screen.getByText('Extracted resume')).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: /continue to job description/i }),
    )

    await user.type(screen.getByLabelText(/^role title$/i), 'Software Engineer')
    await user.type(
      screen.getByRole('textbox', { name: /^job description$/i }),
      'Build APIs with Python',
    )
    await user.click(
      screen.getByRole('button', { name: /save and extract/i }),
    )

    expect(
      await screen.findByText('Extracted job description'),
    ).toBeInTheDocument()
    expect(screen.getByText('SQL')).toBeInTheDocument()
    expect(screen.getByText('Own services')).toBeInTheDocument()
    expect(screen.getByText('mid')).toBeInTheDocument()

    const createCall = vi.mocked(fetch).mock.calls[0]
    expect(createCall[0]).toBe('http://localhost:8000/job-descriptions')
    expect(JSON.parse(createCall[1]?.body as string)).toEqual({
      raw_text: 'Build APIs with Python',
      company_id: 10,
      role_title: 'Software Engineer',
    })
    expect(
      JSON.parse(sessionStorage.getItem(DISCOVERY_FLOW_KEY)!).jobDescription.id,
    ).toBe(3)
  })

  it('rehydrates to FRAME 4 when sessionStorage has resume extract result', () => {
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
        resume: {
          id: 7,
          user_id: 1,
          raw_text: 'Jane',
          extracted_data: {
            skills: ['TypeScript'],
            experience: [],
            education: [],
          },
          created_at: '2026-08-03T00:00:00Z',
        },
        jobDescription: null,
      }),
    )

    renderHome()

    expect(screen.getByText('Extracted resume')).toBeInTheDocument()
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
    expect(screen.queryByText('Alex Recruiter')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('rehydrates to FRAME 5 when sessionStorage has resume + JD extract results', () => {
    sessionStorage.setItem(
      DISCOVERY_FLOW_KEY,
      JSON.stringify({
        company: { name: 'Acme Inc', domain: 'acme.com' },
        discoveryResult: sampleContact,
        resume: {
          id: 7,
          user_id: 1,
          raw_text: 'Jane',
          extracted_data: {
            skills: ['Python'],
            experience: [],
            education: [],
          },
          created_at: '2026-08-03T00:00:00Z',
        },
        jobDescription: {
          id: 3,
          user_id: 1,
          company_id: 10,
          role_title: 'Engineer',
          raw_text: 'JD text',
          extracted_data: {
            required_skills: ['Go'],
            responsibilities: ['Ship'],
            seniority_level: 'senior',
          },
          created_at: '2026-08-03T00:00:00Z',
        },
      }),
    )

    renderHome()

    expect(screen.getByText('Extracted job description')).toBeInTheDocument()
    expect(screen.getByText('Go')).toBeInTheDocument()
    expect(screen.getByText('senior')).toBeInTheDocument()
    expect(screen.queryByText('Extracted resume')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })
})
