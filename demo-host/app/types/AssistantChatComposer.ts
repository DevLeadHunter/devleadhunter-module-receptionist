import type { AssistantWidgetLang } from '~/types/AiAssistant'

export type AssistantChatComposerProps = {
  lang: AssistantWidgetLang
  modelValue: string
  isBusy: boolean
  canSendPhoto: boolean
  canBook: boolean
}

export type AssistantChatComposerEmits = {
  'update:modelValue': [text: string]
  send: []
  photo: []
  appointment: []
}
