import type { AiAssistantSummary } from '~/types/AiAssistant'

export type AssistantVideoBuildStatus = 'done' | 'unavailable' | 'failed'

export type AssistantVideoBuildResult = {
  status: AssistantVideoBuildStatus
  assistant?: AiAssistantSummary
  message?: string
}

export type AssistantPreviewTimingOverrides = {
  presenter_duration: number
  presenter_intro: number
  presenter_outro: number
  total_seconds: number
}

export type AssistantPreviewVideoResult = {
  status: AssistantVideoBuildStatus
  video?: Blob
  message?: string
}

export type AssistantSidecarBuildResult = {
  status: AssistantVideoBuildStatus
  blob?: Blob
  message?: string
}
