import type { AiAssistantSummary, AssistantSubscriptionInterval } from './AiAssistant'

export type AssistantSubscriptionCardProps = {
  assistant: AiAssistantSummary
  isFramed?: boolean
}

export type AssistantSubscriptionLinkForManualCopy = {
  interval: AssistantSubscriptionInterval
  url: string
}
