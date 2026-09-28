import type { AiAssistantConfig } from '~/types/AiAssistant'

/** Props of the demo page that sells a receptionist to the business it was prepared for. */
export type AssistantDemoPageProps = {
  assistant: AiAssistantConfig
  isJustSubscribed: boolean
}
