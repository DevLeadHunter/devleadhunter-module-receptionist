import type { AssistantWidgetLanguage } from './AiAssistant'

/** What the visitor types to be called back. */
export type AssistantContactDetails = {
  name: string
  contact: string
  need: string
}

export type AssistantChatContactFormProps = {
  language: AssistantWidgetLanguage
  pickedSummary: string
  initialName: string
  initialContact: string
  initialNeed: string
  isSubmitting: boolean
}

export type AssistantChatContactFormEmits = {
  submit: [details: AssistantContactDetails]
  cancel: []
}
