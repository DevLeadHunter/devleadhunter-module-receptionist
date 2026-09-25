import type { AiAssistantSummary } from '~/types/AiAssistant'

/** Props of the assistant summary card of the « Assistants IA » list. */
export type AiAssistantCardProps = {
  assistant: AiAssistantSummary
}

/** Events the card emits: copy the demo link, open the demo in a new tab. */
export type AiAssistantCardEmits = {
  copy: [url: string]
  open: [url: string]
}
