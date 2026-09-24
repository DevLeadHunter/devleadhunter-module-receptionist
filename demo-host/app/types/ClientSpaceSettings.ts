import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
} from '~/types/AiAssistantClientSpace'

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
