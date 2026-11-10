import type { AiAssistantSummary } from './AiAssistant'

export type AiAssistantCardProps = {
  assistant: AiAssistantSummary
}

export type AiAssistantCardEmits = {
  open: [url: string]
}
