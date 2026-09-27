import type { AiAssistantClientLimit, AiAssistantClientLimitUpdate } from '~/types/AiAssistantClientSpace'

/** Props of the client-space limits form. */
export type ClientSpaceLimitsProps = {
  limits: AiAssistantClientLimit[]
  assistantName: string
  isSaving: boolean
  errorMessage: string | null
  hasSaved: boolean
  readOnly: boolean
}

/** Events of the ClientSpaceLimits component. */
export type ClientSpaceLimitsEmits = {
  save: [updates: AiAssistantClientLimitUpdate[]]
}
