import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientRequestType,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
  AiAssistantClientTestSmsState,
} from '~/types/AiAssistantClientSpace'

/** Which half of the settings a screen edits: the receptionist herself, or how the business is alerted. */
export type ClientSpaceSettingsPart = 'assistant' | 'alerts'

/** A request type a client can have texted at once, with its label. */
export type ClientSpaceRequestTypeOption = {
  value: AiAssistantClientRequestType
  label: string
}

/** Props of the client-space settings form. */
export type ClientSpaceSettingsProps = {
  part: ClientSpaceSettingsPart
  settings: AiAssistantClientSettings
  languageOptions: AiAssistantClientLanguageOption[]
  isSaving: boolean
  errorMessage: string | null
  hasSaved: boolean
  readOnly: boolean
  /** The test SMS to the saved alert mobile: where it stands, and what to say about it. */
  testSmsState: AiAssistantClientTestSmsState
  testSmsMessage: string | null
}

/** Events of the ClientSpaceSettings component. */
export type ClientSpaceSettingsEmits = {
  save: [update: AiAssistantClientSettingsUpdate]
  'test-sms': []
}
