import type { AssistantWidgetLang } from '~/types/AiAssistant'

/** `canPlayExample`: the demo page offers to play a conversation by itself before the visitor writes. */
export type AssistantChatQuickRepliesProps = {
  lang: AssistantWidgetLang
  suggestions: string[]
  canSendPhoto: boolean
  canPlayExample: boolean
}

export type AssistantChatQuickRepliesEmits = {
  photo: []
  appointment: []
  suggest: [text: string]
  example: []
}
