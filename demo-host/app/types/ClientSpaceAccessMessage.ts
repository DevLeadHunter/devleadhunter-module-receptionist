import type { AiAssistantClientRenewState, AiAssistantClientSpaceState } from '~/types/AiAssistantClientSpace'

export type ClientSpaceAccessMessageProps = {
  state: AiAssistantClientSpaceState
  renewState: AiAssistantClientRenewState
}

export type ClientSpaceAccessMessageEmits = {
  renew: []
}
