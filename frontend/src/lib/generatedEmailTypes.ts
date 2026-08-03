/**
 * Types mirroring backend GeneratedEmail* / MatchData / Eval* Out schemas
 * (verified against backend/app/schemas/generated_email.py).
 *
 * EvalGatesOut omits violation_detail — do not invent or display it client-side.
 */

export type SkillMatch = {
  jd_requirement: string
  matched: boolean
  resume_evidence: string | null
}

export type ExperienceAlignment = {
  jd_responsibility: string
  resume_evidence: string | null
  strength: 'strong' | 'partial' | 'none'
}

export type MatchData = {
  skill_matches: SkillMatch[]
  experience_alignment: ExperienceAlignment[]
  unmatched_jd_requirements: string[]
  notable_resume_strengths: string[]
  overall_match_summary: string
}

export type EvalGatesOut = {
  no_unsupported_claims: boolean
  correct_contact_name_used: boolean
  no_unprompted_gap_admission: boolean
}

export type EvalDimensions = {
  role_company_specificity: number
  relevance_alignment: number
  tone_professionalism: number
  conciseness: number
  clear_cta: number
}

export type EvalBreakdownOut = {
  gates: EvalGatesOut
  dimensions: EvalDimensions
}

export type GenerateEmailRequest = {
  contact_id: number
  resume_id: number
  job_description_id: number
}

export type GeneratedEmailOut = {
  id: number
  contact_id: number
  resume_id: number
  job_description_id: number
  subject: string
  body: string
  eval_score: number
  eval_breakdown: EvalBreakdownOut
  match_data: MatchData
  gate_passed: boolean
  created_at: string
}
