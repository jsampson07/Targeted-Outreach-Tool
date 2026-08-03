import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { extractResume, uploadResume } from '../lib/documentApi'
import type { ResumeOut } from '../lib/documentTypes'
import { ApiError } from '../lib/apiClient'
import { validateResumeFile } from '../lib/resumeValidation'

export type UseResumeForGenerationResult = {
  /** Post-extract resume when ready; null until upload+extract succeeds. */
  resume: ResumeOut | null
  /** Convenience for generate-email callers — same isolation boundary. */
  resumeId: number | null
  isPending: boolean
  error: string | null
  /**
   * Option 2: upload a fresh file and run extract. Later Option 3 (picker)
   * swaps this hook's internals; callers keep using resume / resumeId.
   */
  obtainFromUpload: (file: File) => void
  reset: () => void
}

type Options = {
  /** Rehydrated post-extract resume from sessionStorage, if any. */
  initialResume?: ResumeOut | null
  onReady?: (resume: ResumeOut) => void
}

/**
 * Isolates "how a resume_id is obtained for this generation" behind one hook.
 *
 * Current implementation (Option 2): upload PDF/DOCX → create → extract every
 * search. A future saved-resume picker (Option 3) should replace the internals
 * of this hook only — not the surrounding frame flow.
 */
export function useResumeForGeneration(
  options: Options = {},
): UseResumeForGenerationResult {
  const { initialResume = null, onReady } = options
  const [resume, setResume] = useState<ResumeOut | null>(initialResume)
  const [clientError, setClientError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const created = await uploadResume(file)
      return extractResume(created.id)
    },
    onSuccess: (extracted) => {
      setClientError(null)
      setResume(extracted)
      onReady?.(extracted)
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setClientError(err.user_message)
      } else {
        setClientError('Something went wrong. Please try again.')
      }
    },
  })

  function obtainFromUpload(file: File) {
    const validationError = validateResumeFile(file)
    if (validationError) {
      setClientError(validationError)
      return
    }
    setClientError(null)
    mutation.mutate(file)
  }

  function reset() {
    setResume(null)
    setClientError(null)
    mutation.reset()
  }

  return {
    resume,
    resumeId: resume?.id ?? null,
    isPending: mutation.isPending,
    error: clientError,
    obtainFromUpload,
    reset,
  }
}
