import type { AiAssistantSummary } from '~/types/AiAssistant'

/** Props of the drawer listing what an assistant's visitors asked (read-only journal). */
export type UiAssistantConversationsDrawerProps = {
  open: boolean
  assistant: AiAssistantSummary | null
  showBack: boolean
}

/** Events the conversations drawer emits. */
export type UiAssistantConversationsDrawerEmits = {
  close: []
  back: []
}
