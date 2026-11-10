import type { AiAssistantConfig } from './AiAssistant'
import type { ClientSpaceIconName } from './ClientSpaceIcon'

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
