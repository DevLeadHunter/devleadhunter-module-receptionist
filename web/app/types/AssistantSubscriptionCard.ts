import type { AiAssistantSummary, AssistantSubscriptionInterval } from '~/types/AiAssistant'

export type AssistantSubscriptionCardProps = {
  assistant: AiAssistantSummary
}

export type AssistantSubscriptionLinkForManualCopy = {
  interval: AssistantSubscriptionInterval
  url: string
}
