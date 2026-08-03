import { request } from './apiClient'
import type {
  JobDescriptionCreate,
  JobDescriptionOut,
  ResumeOut,
} from './documentTypes'

/**
 * Upload a resume PDF/DOCX. Backend contract (verified): multipart field name
 * ``file`` on ``POST /resumes`` — not JSON ``ResumeCreate{raw_text}``.
 */
export function uploadResume(file: File): Promise<ResumeOut> {
  const body = new FormData()
  body.append('file', file)
  return request<ResumeOut>('/resumes', {
    method: 'POST',
    body,
  })
}

export function extractResume(resumeId: number): Promise<ResumeOut> {
  return request<ResumeOut>(`/resumes/${resumeId}/extract`, {
    method: 'POST',
  })
}

export function createJobDescription(
  payload: JobDescriptionCreate,
): Promise<JobDescriptionOut> {
  return request<JobDescriptionOut>('/job-descriptions', {
    method: 'POST',
    body: payload,
  })
}

export function extractJobDescription(jdId: number): Promise<JobDescriptionOut> {
  return request<JobDescriptionOut>(`/job-descriptions/${jdId}/extract`, {
    method: 'POST',
  })
}
