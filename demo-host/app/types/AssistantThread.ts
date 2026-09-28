import type { Ref } from 'vue'
import type { AiAssistantConfig, AssistantChatMessage, AssistantWidgetLanguage } from '~/types/AiAssistant'

/** The card open in the thread, at most one at a time. */
export type AssistantThreadPanel = 'photo' | 'slots' | 'lead-form'

/** The state the parts of a conversation share: the thread, its language and session, and what is open in it. */
export type AssistantThreadContext = {
  assistant: AiAssistantConfig
  publicEndpoint: string
  messages: Ref<AssistantChatMessage[]>
  language: Ref<AssistantWidgetLanguage>
  sessionId: Ref<string>
  isBusy: Ref<boolean>
  openPanel: Ref<AssistantThreadPanel | null>
  hasSentLead: Ref<boolean>
  noteInlineOpening: () => void
}

/** A conversation as the widget or the host page stored it, read back field by field. */
export type AssistantStoredConversation = {
  language: string | null
  sessionId: string | null
  messages: AssistantChatMessage[]
}
