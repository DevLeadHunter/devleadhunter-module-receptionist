import type { AiAssistantClientRenewState, AiAssistantClientSpaceState } from './AiAssistantClientSpace'

export type ClientSpaceAccessMessageProps = {
  state: AiAssistantClientSpaceState
  renewState: AiAssistantClientRenewState
}

export type ClientSpaceAccessMessageEmits = {
  renew: []
}
