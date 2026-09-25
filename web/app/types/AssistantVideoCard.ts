import type { AiAssistantSummary } from '~/types/AiAssistant'

export type AssistantVideoCardProps = {
  assistant: AiAssistantSummary
  isBusy: boolean
}

export type AssistantVideoCardEmits = {
  generate: []
}
