import type { AssistantWidgetLang } from '~/types/AiAssistant'

/** The two actions the bar offers besides sending a message. */
export type AssistantChatComposerTool = 'photo' | 'appointment'

export type AssistantChatComposerProps = {
  lang: AssistantWidgetLang
  modelValue: string
  isBusy: boolean
  canSendPhoto: boolean
  canBook: boolean
  /** A narrow bar (a phone): the two actions fold behind one « + » so the field keeps its width. */
  isCompact: boolean
}

export type AssistantChatComposerEmits = {
  'update:modelValue': [text: string]
  send: []
  photo: []
  appointment: []
}
