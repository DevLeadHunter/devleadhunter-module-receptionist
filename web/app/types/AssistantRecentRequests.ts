import type { AiAssistantRequestItem } from './AiAssistant'

export type AssistantRecentRequestsProps = {
  assistantId: number
  assistantName: string
  requests: AiAssistantRequestItem[]
}

export type AssistantRecentRequestsEmits = {
  open: [request: AiAssistantRequestItem]
}
