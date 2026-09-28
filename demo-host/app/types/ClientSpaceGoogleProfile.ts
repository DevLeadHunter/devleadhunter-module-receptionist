import type { AiAssistantClientGoogleProfile } from '~/types/AiAssistantClientSpace'

export type ClientSpaceGoogleProfileProps = {
  googleProfile: AiAssistantClientGoogleProfile
  assistantName: string
  isSaving: boolean
  errorMessage: string | null
  readOnly: boolean
}

export type ClientSpaceGoogleProfileEmits = {
  linked: [isLinked: boolean]
}
