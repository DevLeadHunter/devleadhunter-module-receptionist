import type { AssistantWidgetLanguage } from '~/types/AiAssistant'

export type AssistantChatLauncherProps = {
  language: AssistantWidgetLanguage
  assistantName: string
  avatarUrl: string
  avatarFallbackUrl: string
  isMobileLayout: boolean
}

export type AssistantChatLauncherEmits = {
  open: []
}
