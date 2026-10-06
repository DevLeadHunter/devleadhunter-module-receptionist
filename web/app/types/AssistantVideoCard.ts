import type { AiAssistantSummary } from '~/types/AiAssistant'

export type AssistantVideoCardProps = {
  assistant: AiAssistantSummary
  isBusy: boolean
  isRemovingVideo: boolean
  isTakingLongerThanExpected: boolean
  isRefreshingVideo: boolean
  isHeadingHidden?: boolean
  isFramed?: boolean
}

export type AssistantVideoCardEmits = {
  generate: []
  'remove-video': []
  'refresh-video': []
}
