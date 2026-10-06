import type { AiAssistantEditForm, AiAssistantSummary } from '~/types/AiAssistant'

/** Which part of the settings the form shows and saves: the identity, or the alerts with the mailbox and the model. */
export type AssistantSettingsFormSection = 'identity' | 'alerts'

/** Props of the form editing an assistant's identity, the alerts its business receives and its model constraints. */
export type AssistantSettingsFormProps = {
  assistant: AiAssistantSummary
  section: AssistantSettingsFormSection
}

/** Events of the settings form; `saved` carries the assistant as the API returned it, `draft` every unsaved edit. */
export type AssistantSettingsFormEmits = {
  saved: [assistant: AiAssistantSummary]
  draft: [form: AiAssistantEditForm]
}

/** Which sections of the form hold an unsaved edit. */
export type AssistantSettingsFormChangedSections = {
  identity: boolean
  alerts: boolean
}
