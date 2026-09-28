import type { AiAssistantSummary } from '~/types/AiAssistant'

export type AiAssistantCardProps = {
  assistant: AiAssistantSummary
}

export type AiAssistantCardEmits = {
  open: [url: string]
}
