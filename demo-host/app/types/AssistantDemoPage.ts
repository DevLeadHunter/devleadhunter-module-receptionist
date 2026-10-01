import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { ClientSpaceIconName } from '~/types/ClientSpaceIcon'

export type AssistantDemoPageProps = {
  assistant: AiAssistantConfig
  isJustSubscribed: boolean
}

/** One short promise of the demo page (under its title, in its lists), with its icon. */
export type AssistantDemoPagePoint = {
  icon: ClientSpaceIconName
  label: string
}

/** One card of what the business receives from its receptionist. */
export type AssistantDemoPageFeature = {
  icon: ClientSpaceIconName
  title: string
  text: string
}
