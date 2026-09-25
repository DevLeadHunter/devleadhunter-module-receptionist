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
  /** The wished half-days or the booked slot, as the widget showed them; empty when none. */
  slots: string
  /** True when the slot was booked in the business's agenda (not only wished). */
  booked: boolean
  hasPhoto: boolean
}

/** Events the widget emits. */
export type AssistantChatEmits = {
  'lead-sent': [summary: AssistantLeadSummary]
}
