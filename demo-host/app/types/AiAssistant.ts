/** Public configuration of a prospect's AI assistant, served by the API and consumed as-is. */
export interface AiAssistantConfig {
  slug: string
  business_name: string
  assistant_name: string
  languages: string[]
  accent_color: string | null
  status: string
  owner_name?: string | null
  owner_profile_photo_url?: string | null
  owner_contact_phone?: string | null
  owner_contact_email?: string | null
  video_available?: boolean
  video_url?: string | null
  video_thumbnail_url?: string | null
}

/** A single conversation turn exchanged with the assistant. */
export interface AssistantChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** The assistant's reply to a chat request. */
export interface AssistantChatReply {
  reply: string
}

/** Localized labels for the lead-capture form. */
export interface AssistantLeadLabels {
  open: string
  title: string
  name: string
  contact: string
  need: string
  send: string
  cancel: string
  sent: string
}

/** Languages the widget offers preset greetings and suggestions for. */
export type AssistantWidgetLang = 'fr' | 'nl' | 'en' | 'de' | 'lu'
