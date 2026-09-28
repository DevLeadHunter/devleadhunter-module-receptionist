import type { Ref } from 'vue'
import type {
  AiAssistantConfig,
  AssistantChatMessage,
  AssistantThreadMessage,
  AssistantWidgetLanguage,
} from '~/types/AiAssistant'
import type { AssistantRequestFailure } from '~/types/AssistantRequest'

/** The card open in the thread, at most one at a time. */
export type AssistantThreadPanel = 'photo' | 'slots' | 'lead-form'

/**
 * The state the parts of a conversation share: the thread, its language and session, what is open in it; and how a
 * part adds one of the widget's own lines, or tells the visitor a call failed.
 */
export type AssistantThreadContext = {
  assistant: AiAssistantConfig
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

/** A conversation as the widget or the host page stored it, read back field by field. */
export type AssistantStoredConversation = {
  language: string | null
  sessionId: string | null
  messages: AssistantChatMessage[]
}
