import type { Ref } from 'vue'
import type { AssistantChatMessage, AssistantThreadMessage, AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantRequestFailure } from '~/types/AssistantRequest'

export type AssistantThreadPanel = 'photo' | 'slots' | 'lead-form'

/** The conversation thread its parts share: its state, and how a part adds a widget line or reports a failed call. */
export type AssistantConversationThread = {
  publicEndpoint: string
  messages: Ref<AssistantThreadMessage[]>
  language: Ref<AssistantWidgetLanguage>
  sessionId: Ref<string>
  isBusy: Ref<boolean>
  openPanel: Ref<AssistantThreadPanel | null>
  hasSentLead: Ref<boolean>
  isAssistantUnavailable: Ref<boolean>
  noteInlineOpening: () => void
  pushLocalLine: (content: string, role?: AssistantThreadMessage['role']) => void
  reportFailure: (failure: AssistantRequestFailure) => void
}

export type AssistantStoredConversation = {
  language: string | null
  sessionId: string | null
  messages: AssistantChatMessage[]
}
