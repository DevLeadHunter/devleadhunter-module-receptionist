import type { AssistantWidgetLang } from '~/types/AiAssistant'

export type AssistantChatLauncherProps = {
  lang: AssistantWidgetLang
  assistantName: string
  avatarUrl: string
  avatarFallbackUrl: string
  isMobileLayout: boolean
}

export type AssistantChatLauncherEmits = {
  open: []
}
