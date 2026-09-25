import type { AssistantWidgetLang } from '~/types/AiAssistant'

/**
 * `canPlayExample`: the demo page offers to play a conversation by itself before the visitor writes;
 * `canBookAppointment` false shows the suggestions alone (the questions a reply offers next).
 */
export type AssistantChatQuickRepliesProps = {
  lang: AssistantWidgetLang
  suggestions: string[]
  canSendPhoto: boolean
  canPlayExample: boolean
  canBookAppointment: boolean
}

export type AssistantChatQuickRepliesEmits = {
  photo: []
  appointment: []
  suggest: [text: string]
  example: []
}
