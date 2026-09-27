import type { AiAssistantClientRequest, AiAssistantClientRequestOutcome } from '~/types/AiAssistantClientSpace'

/** Props of the client-space request detail. */
export type ClientSpaceRequestDetailProps = {
  request: AiAssistantClientRequest
  /** A call about this request is in flight. */
  isBusy: boolean
  errorMessage: string | null
  /** The example space: shown, never changed. */
  readOnly: boolean
  /** On a phone, the detail replaces the list and shows a way back. */
  showBack: boolean
}

/** One line of the event block: what the visitor said of the date, the place, the guests or the budget. */
export type ClientSpaceRequestEventRow = {
  label: string
  value: string
}

/** Events of the ClientSpaceRequestDetail component. */
export type ClientSpaceRequestDetailEmits = {
  handled: [requestId: number]
  dropped: [requestId: number]
  outcome: [requestId: number, outcome: AiAssistantClientRequestOutcome | null]
  back: []
}
