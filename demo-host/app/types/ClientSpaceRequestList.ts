import type { AiAssistantClientRequest, AiAssistantClientUnansweredEntry } from '~/types/AiAssistantClientSpace'

/** Which requests the list shows. */
export type ClientSpaceRequestFilter = 'pending' | 'done' | 'all'

/** The short status at the right of a request row, and its colour. */
export type ClientSpaceRequestStatus = {
  label: string
  tone: 'red' | 'accent' | 'green' | 'grey' | 'amber'
}

/** The requests of one business-time day. */
export type ClientSpaceRequestDayGroup = {
  day: string
  label: string
  requests: AiAssistantClientRequest[]
}

/** Props of the client-space request list. */
export type ClientSpaceRequestListProps = {
  requests: AiAssistantClientRequest[]
  unanswered: AiAssistantClientUnansweredEntry[]
  assistantName: string
  portraitUrl: string
  portraitFallbackUrl: string
  /** The request open beside the list on a wide screen, highlighted. */
  activeRequestId: number | null
  activeQuestionIndex: number | null
}

/** Events of the ClientSpaceRequestList component. */
export type ClientSpaceRequestListEmits = {
  open: [requestId: number]
  'open-question': [index: number]
}
