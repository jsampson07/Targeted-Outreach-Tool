import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../context/AuthContext'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '../lib/apiClient'
import type { AnalyticsSummary } from '../lib/analyticsTypes'
import { AnalyticsPage } from './AnalyticsPage'

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

const summaryWithData: AnalyticsSummary = {
  total_sent: 9,
  total_replied: 3,
  overall_reply_rate: 3 / 9,
  by_confidence_tier: [
    {
      tier: 'verified',
      sent: 6,
      replied: 3,
      reply_rate: 0.5,
    },
    {
      tier: 'pattern_guessed',
      sent: 3,
      replied: 0,
      reply_rate: 0.0,
    },
  ],
  by_eval_score_bucket: [
    {
      bucket: '<3',
      sent: 2,
      replied: 0,
      reply_rate: 0.0,
    },
    {
      bucket: '3-4',
      sent: 4,
      replied: 1,
      reply_rate: 0.25,
    },
    {
      bucket: '4+',
      sent: 3,
      replied: 2,
      reply_rate: 2 / 3,
    },
  ],
}

const emptySummary: AnalyticsSummary = {
  total_sent: 0,
  total_replied: 0,
  overall_reply_rate: null,
  by_confidence_tier: [],
  by_eval_score_bucket: [],
}

function mockSummary(summary: AnalyticsSummary) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/analytics/summary')) {
      return jsonResponse(summary)
    }
    return jsonResponse({ user_message: 'Unexpected', error_code: 'Test' }, 500)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderAnalytics() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter>
          <AnalyticsPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('AnalyticsPage', () => {
  beforeEach(() => {
    seedAuth()
  })

  afterEach(() => {
    cleanup()
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('renders overall rate with n= and both breakdowns', async () => {
    mockSummary(summaryWithData)
    renderAnalytics()

    await waitFor(() => {
      expect(
        screen.getByText(/3\/9 replied \(33%\)/i),
      ).toBeInTheDocument()
    })
    expect(screen.getByText(/\(n=9\)/)).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: /by contact confidence tier/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/verified/i)).toBeInTheDocument()
    expect(screen.getByText(/pattern guessed/i)).toBeInTheDocument()
    expect(screen.getByText(/\(n=6; 3\/6 replied\)/)).toBeInTheDocument()
    // Real measured zero (sent>0, replied=0) is shown:
    expect(screen.getByText(/\(n=3; 0\/3 replied\)/)).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: /by email eval score/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('<3')).toBeInTheDocument()
    expect(screen.getByText('3-4')).toBeInTheDocument()
    expect(screen.getByText('4+')).toBeInTheDocument()
  })

  it('shows no-sent message when overall_reply_rate is null', async () => {
    mockSummary(emptySummary)
    renderAnalytics()

    await waitFor(() => {
      expect(
        screen.getByText(/no sent emails logged yet/i),
      ).toBeInTheDocument()
    })
    expect(screen.queryByText(/0%|0\/0/)).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: /overall reply rate/i }),
    ).not.toBeInTheDocument()
  })

  it('does not invent a zero-sent bucket row (API omits them)', async () => {
    // Only verified + 4+ present — catch_all / <3 / 3-4 omitted by API.
    mockSummary({
      total_sent: 2,
      total_replied: 1,
      overall_reply_rate: 0.5,
      by_confidence_tier: [
        {
          tier: 'verified',
          sent: 2,
          replied: 1,
          reply_rate: 0.5,
        },
      ],
      by_eval_score_bucket: [
        {
          bucket: '4+',
          sent: 2,
          replied: 1,
          reply_rate: 0.5,
        },
      ],
    })
    renderAnalytics()

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /overall reply rate/i }),
      ).toBeInTheDocument()
    })
    expect(screen.getByText(/1\/2 replied \(50%\)/i)).toBeInTheDocument()
    expect(screen.queryByText(/catch all/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/unknown/i)).not.toBeInTheDocument()
    expect(screen.queryByText('<3')).not.toBeInTheDocument()
    expect(screen.queryByText('3-4')).not.toBeInTheDocument()
    expect(screen.getByText('4+')).toBeInTheDocument()
  })
})
