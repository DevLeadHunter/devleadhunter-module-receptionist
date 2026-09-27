import type { AiAssistantClientUnansweredEntry } from '~/types/AiAssistantClientSpace'

/** Props of one of the receptionist's questions, opened to answer it. */
export type ClientSpaceQuestionProps = {
  entry: AiAssistantClientUnansweredEntry
  assistantName: string
  portraitUrl: string
  portraitFallbackUrl: string
  isBusy: boolean
  errorMessage: string | null
  readOnly: boolean
  showBack: boolean
}

/** Events of the ClientSpaceQuestion component. */
export type ClientSpaceQuestionEmits = {
  answer: [answer: string]
  dismiss: []
  back: []
}
