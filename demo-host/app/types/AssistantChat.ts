import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantHostPage } from '~/types/AssistantDemoScript'

/**
 * Props of the AssistantChat widget; `inline` renders the open panel in place (the demo page's phone), `hostPage`
 * is the client's page the loader embedded it on (the greeting adapts to it).
 */
export type AssistantChatProps = {
  config: AiAssistantConfig
  inline: boolean
  hostPage: AssistantHostPage | null
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

/** Events the widget emits; `example-played` once the demo page's scripted conversation has run. */
export type AssistantChatEmits = {
  'lead-sent': [summary: AssistantLeadSummary]
  'example-played': []
}
