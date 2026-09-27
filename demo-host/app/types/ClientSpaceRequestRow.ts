import type { AiAssistantClientRequest } from '~/types/AiAssistantClientSpace'

/** Props of one request row of the client space. */
export type ClientSpaceRequestRowProps = {
  request: AiAssistantClientRequest
  /** Open beside the list on a wide screen. */
  active: boolean
}

/** Events of the ClientSpaceRequestRow component. */
export type ClientSpaceRequestRowEmits = {
  select: [requestId: number]
}
