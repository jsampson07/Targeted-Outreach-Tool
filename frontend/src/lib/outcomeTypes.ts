/** Types mirroring backend OutcomeCreate / OutcomeOut (DATA_MODEL.md §2.8). */

export type OutcomeEventType =
  | 'sent'
  | 'no_response'
  | 'replied'
  | 'interview'

export type OutcomeCreate = {
  generated_email_id: number
  event_type: OutcomeEventType
}

export type OutcomeOut = {
  id: number
  generated_email_id: number
  event_type: OutcomeEventType
  occurred_at: string
}
