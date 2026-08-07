/** Types mirroring backend AnalyticsSummary schemas (DATA_MODEL.md §2.10). */

import type { VerificationTier } from './discoveryTypes'

export type EvalScoreBucket = '<3' | '3-4' | '4+'

export type ConfidenceTierBreakdown = {
  tier: VerificationTier
  sent: number
  replied: number
  reply_rate: number
}

export type EvalScoreBucketBreakdown = {
  bucket: EvalScoreBucket
  sent: number
  replied: number
  reply_rate: number
}

export type AnalyticsSummary = {
  total_sent: number
  total_replied: number
  overall_reply_rate: number | null
  by_confidence_tier: ConfidenceTierBreakdown[]
  by_eval_score_bucket: EvalScoreBucketBreakdown[]
}
