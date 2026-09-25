import type { AiAssistantSummary } from '~/types/AiAssistant'

/** Props of the form editing an assistant's identity, the alerts its business receives and its model constraints. */
export type AssistantSettingsFormProps = {
  assistant: AiAssistantSummary
}

/** Events of the settings form; `saved` carries the assistant as the API returned it. */
export type AssistantSettingsFormEmits = {
  saved: [assistant: AiAssistantSummary]
}
