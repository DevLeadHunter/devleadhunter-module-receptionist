import type { AssistantWidgetLang } from '~/types/AiAssistant'

/** What the visitor types to be called back. */
export type AssistantContactDetails = {
  name: string
  contact: string
  need: string
}

export type AssistantChatContactFormProps = {
  lang: AssistantWidgetLang
  pickedSummary: string
  initialNeed: string
  isSubmitting: boolean
}

export type AssistantChatContactFormEmits = {
  submit: [details: AssistantContactDetails]
  cancel: []
}
