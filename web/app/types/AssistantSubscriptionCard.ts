import type { AiAssistantSummary, AssistantSubscriptionInterval } from '~/types/AiAssistant'

export type AssistantSubscriptionCardProps = {
  assistant: AiAssistantSummary
  isFramed?: boolean
}

export type AssistantSubscriptionLinkForManualCopy = {
  interval: AssistantSubscriptionInterval
  url: string
}
