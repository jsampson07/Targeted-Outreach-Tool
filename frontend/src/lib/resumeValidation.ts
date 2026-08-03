import {
  RESUME_ALLOWED_EXTENSIONS,
  RESUME_MAX_UPLOAD_BYTES,
} from './documentTypes'

/**
 * Client-side checks mirroring app/services/resume.py limits so the UI can
 * surface a clear error before a 422. The 50-char minimum is post-parse on
 * the server (depends on PDF/DOCX text extraction) — not fully checkable here.
 */
export function validateResumeFile(file: File): string | null {
  const lower = file.name.toLowerCase()
  const allowed = RESUME_ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))
  if (!allowed) {
    return 'Only PDF and DOCX files are accepted.'
  }
  if (file.size > RESUME_MAX_UPLOAD_BYTES) {
    return 'File too large (maximum 2MB).'
  }
  return null
}
