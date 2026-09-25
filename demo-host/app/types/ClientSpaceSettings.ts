import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientRequestType,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
} from '~/types/AiAssistantClientSpace'

/** A request type the client can have texted at once, with its French label. */
export type ClientSpaceRequestTypeOption = {
  value: AiAssistantClientRequestType
  label: string
}

/** Props of the client-space settings form. */
export type ClientSpaceSettingsProps = {
  settings: AiAssistantClientSettings
  languageOptions: AiAssistantClientLanguageOption[]
  isSaving: boolean
  errorMessage: string | null
  hasSaved: boolean
}

/** Events of the ClientSpaceSettings component. */
export type ClientSpaceSettingsEmits = {
  save: [update: AiAssistantClientSettingsUpdate]
}
