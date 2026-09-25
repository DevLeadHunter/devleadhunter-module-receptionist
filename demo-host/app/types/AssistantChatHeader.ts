import type { AssistantWidgetLang } from '~/types/AiAssistant'

export type AssistantChatHeaderProps = {
  assistantName: string
  businessName: string
  roleLabel: string
  onlineLabel: string
  avatarUrl: string
  avatarFallbackUrl: string
  canClose: boolean
  lang: AssistantWidgetLang
  languages: AssistantWidgetLang[]
}

export type AssistantChatHeaderEmits = {
  close: []
  'change-lang': [code: AssistantWidgetLang]
}
