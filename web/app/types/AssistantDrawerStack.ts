import type { AiAssistantRequestItem, AiAssistantSummary, AssistantSubscription } from './AiAssistant'

/** A sold-assistant subscription's detail drawer (view + cancel/refund). */
export type AssistantSubscriptionDrawerEntry = {
  kind: 'assistant-subscription'
  subscription: AssistantSubscription
}

/** The read-only journal of what an assistant's visitors asked. */
export type AssistantConversationsDrawerEntry = {
  kind: 'assistant-conversations'
  assistant: AiAssistantSummary
}

/** What an assistant reads: its website, its Google listing, its documents. */
export type AssistantSourcesDrawerEntry = {
  kind: 'assistant-sources'
  assistant: AiAssistantSummary
}

/** One visitor request: its details, the conversation it came out of, and the owner's actions on it. */
export type AssistantRequestDrawerEntry = {
  kind: 'assistant-request'
  request: AiAssistantRequestItem
}

/** Cross-page notice describing the latest assistant-subscription mutation done from a drawer. */
export type AssistantSubscriptionMutationNotice = { type: 'updated'; subscription: AssistantSubscription }

/** Cross-page notice describing the latest assistant mutation done from a drawer or a page. */
export type AssistantMutationNotice =
  | { type: 'updated'; assistant: AiAssistantSummary }
  | { type: 'deleted'; assistantId: number }

/** Cross-page notice describing the latest change to a visitor request done from its drawer. */
export type AssistantRequestMutationNotice = { type: 'updated'; request: AiAssistantRequestItem }

declare module '~/types/DrawerStack' {
  interface ModuleDrawerEntries {
    'assistant-subscription': AssistantSubscriptionDrawerEntry
    'assistant-conversations': AssistantConversationsDrawerEntry
    'assistant-sources': AssistantSourcesDrawerEntry
    'assistant-request': AssistantRequestDrawerEntry
  }

  interface DrawerStackChangeNotices {
    assistants: AssistantMutationNotice
    'assistant-requests': AssistantRequestMutationNotice
    'assistant-subscriptions': AssistantSubscriptionMutationNotice
  }
}
