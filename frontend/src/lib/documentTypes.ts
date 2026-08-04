/** Types mirroring backend Resume* / JobDescription* schemas (verified against code). */

export type ExperienceEntry = {
  company: string
  title: string
  start_date: string
  end_date: string | null
  bullet_points: string[]
}

export type ProjectEntry = {
  name: string
  description: string | null
  technologies: string[]
  bullet_points: string[]
}

export type ResumeExtraction = {
  skills: string[]
  experience: ExperienceEntry[]
  education: string[]
  candidate_name: string | null
  projects: ProjectEntry[]
}

export type ResumeOut = {
  id: number
  user_id: number
  raw_text: string
  extracted_data: ResumeExtraction | null
  created_at: string
}

export type JDExtraction = {
  required_skills: string[]
  responsibilities: string[]
  seniority_level: string | null
}

export type JobDescriptionCreate = {
  raw_text: string
  company_id: number
  role_title: string
}

export type JobDescriptionOut = {
  id: number
  user_id: number
  company_id: number
  role_title: string
  raw_text: string
  extracted_data: JDExtraction | null
  created_at: string
}

/** Client-side mirrors of resume upload limits in app/services/resume.py */
export const RESUME_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
export const RESUME_ALLOWED_EXTENSIONS = ['.pdf', '.docx'] as const
