import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { ClientSpaceIconName } from '~/types/ClientSpaceIcon'

export type AssistantDemoPageProps = {
  assistant: AiAssistantConfig
  isJustSubscribed: boolean
}

export type AssistantDemoPagePoint = {
  icon: ClientSpaceIconName
  label: string
}

export type AssistantDemoPageFeature = {
  icon: ClientSpaceIconName
  title: string
  text: string
}
