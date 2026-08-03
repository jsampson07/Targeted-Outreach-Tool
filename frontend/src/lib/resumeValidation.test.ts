import { describe, expect, it } from 'vitest'

import { validateResumeFile } from './resumeValidation'

describe('validateResumeFile', () => {
  it('accepts a small pdf', () => {
    const file = new File(['hello'], 'resume.pdf', { type: 'application/pdf' })
    expect(validateResumeFile(file)).toBeNull()
  })

  it('rejects non pdf/docx extensions', () => {
    const file = new File(['hello'], 'resume.txt', { type: 'text/plain' })
    expect(validateResumeFile(file)).toBe(
      'Only PDF and DOCX files are accepted.',
    )
  })

  it('rejects files over 2MB', () => {
    const file = new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'huge.pdf', {
      type: 'application/pdf',
    })
    expect(validateResumeFile(file)).toBe('File too large (maximum 2MB).')
  })
})
