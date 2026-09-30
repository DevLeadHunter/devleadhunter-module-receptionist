import type { AiAssistantClientMailbox } from '~/types/AiAssistantClientSpace'

export type ClientSpaceMailboxProps = {
  mailbox: AiAssistantClientMailbox
  assistantName: string
  isBusy: boolean
  errorMessage: string | null
  readOnly: boolean
}

export type ClientSpaceMailboxEmits = {
  connect: []
  disconnect: []
}
