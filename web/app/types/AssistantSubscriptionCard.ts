import type { AiAssistantSummary, AssistantSubscriptionInterval } from '~/types/AiAssistant'

export type AssistantSubscriptionCardProps = {
  assistant: AiAssistantSummary
}

export type AssistantSubscriptionLinkToCopy = {
  interval: AssistantSubscriptionInterval
  url: string
}
