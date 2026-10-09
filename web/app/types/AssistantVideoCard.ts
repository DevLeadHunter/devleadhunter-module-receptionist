import type { AiAssistantSummary } from '~/types/AiAssistant'

export type AssistantVideoCardProps = {
  assistant: AiAssistantSummary
  isBusy: boolean
  isRemovingVideo: boolean
  isDesktopAppOnline: boolean
  isCancellingDesktopRequest: boolean
  isHeadingHidden?: boolean
  isFramed?: boolean
}

export type AssistantVideoCardEmits = {
  generate: []
  'remove-video': []
  'cancel-desktop-request': []
}
