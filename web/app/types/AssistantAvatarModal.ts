import type { AiAssistantSummary } from '~/types/AiAssistant'

/** Props of the dialog where the business's own image is sent, chosen or deleted; `accentColor` paints its disc. */
export type AssistantAvatarModalProps = {
  open: boolean
  assistant: AiAssistantSummary
  accentColor: string | null
}

/** Events of the dialog; `updated` carries the assistant as the API returned it. */
export type AssistantAvatarModalEmits = {
  close: []
  updated: [assistant: AiAssistantSummary]
}
