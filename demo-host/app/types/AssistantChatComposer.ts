import type { AssistantWidgetLanguage } from '~/types/AiAssistant'

/** The two actions the bar offers besides sending a message. */
export type AssistantChatComposerTool = 'photo' | 'appointment'

export type AssistantChatComposerProps = {
  language: AssistantWidgetLanguage
  modelValue: string
  isBusy: boolean
  canSendPhoto: boolean
  canBook: boolean
  isCompact: boolean
}

export type AssistantChatComposerEmits = {
  'update:modelValue': [text: string]
  send: []
  photo: []
  appointment: []
}
