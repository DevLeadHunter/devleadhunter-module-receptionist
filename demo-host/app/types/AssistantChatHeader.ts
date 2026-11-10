import type { AssistantWidgetLanguage } from './AiAssistant'

export type AssistantChatHeaderProps = {
  assistantName: string
  businessName: string
  roleLabel: string
  onlineLabel: string
  avatarUrl: string
  avatarFallbackUrl: string
  canClose: boolean
  language: AssistantWidgetLanguage
  languages: AssistantWidgetLanguage[]
}

export type AssistantChatHeaderEmits = {
  close: []
  'change-language': [language: AssistantWidgetLanguage]
}
