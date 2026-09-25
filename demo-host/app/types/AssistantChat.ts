import type { AiAssistantConfig } from '~/types/AiAssistant'

/** Props of the AssistantChat widget; `inline` renders the open panel in place (the demo page's phone). */
export type AssistantChatProps = {
  config: AiAssistantConfig
  inline: boolean
}

/** What a request the visitor just left holds, for the page that shows the business's side of it. */
export type AssistantLeadSummary = {
  name: string
  contact: string
  need: string
  kind: 'appointment' | 'quote' | 'question'
  slots: string
  booked: boolean
  hasPhoto: boolean
}

/** Events the widget emits. */
export type AssistantChatEmits = {
  'lead-sent': [summary: AssistantLeadSummary]
}
