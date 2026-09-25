import type { AssistantWidgetLang } from '~/types/AiAssistant'

export type AssistantChatQuickRepliesProps = {
  lang: AssistantWidgetLang
  suggestions: string[]
  canSendPhoto: boolean
}

export type AssistantChatQuickRepliesEmits = {
  photo: []
  appointment: []
  suggest: [text: string]
  callback: []
}
