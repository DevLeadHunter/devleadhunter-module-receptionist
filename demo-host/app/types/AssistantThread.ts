import type { Ref } from 'vue'
import type {
  AiAssistantConfig,
  AssistantChatMessage,
  AssistantThreadMessage,
  AssistantWidgetLanguage,
} from '~/types/AiAssistant'
import type { AssistantRequestFailure } from '~/types/AssistantRequest'

export type AssistantThreadPanel = 'photo' | 'slots' | 'lead-form'

/** The thread state the conversation's parts share, and how they add a widget line or report a failed call. */
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

export type AssistantStoredConversation = {
  language: string | null
  sessionId: string | null
  messages: AssistantChatMessage[]
}
