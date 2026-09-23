/** An AI assistant generated for a prospect, as seen by its owner. */
export interface AiAssistantSummary {
  id: number
  slug: string
  prospect_id: number | null
  business_name: string
  assistant_name: string
  languages: string[]
  tone: string | null
  accent_color: string | null
  use_brand_color: boolean
  status: string
  demo_url: string
  embed_snippet: string
  video_status: string | null
  video_page_url: string | null
  video_error: string | null
  subscription_status: string | null
  subscription_amount_cents: number | null
  subscription_interval: string | null
  created_at: string
}

/** The current user's assistants. */
export interface AiAssistantListResponse {
  assistants: AiAssistantSummary[]
}

/** A client's recurring subscription to a sold assistant, as the Abonnements page shows it. */
export type AssistantSubscription = {
  id: number
  ai_assistant_id: number | null
  prospect_id: number | null
  business_name: string | null
  assistant_name: string | null
  client_name: string | null
  client_email: string | null
  interval: string
  amount_cents: number
  currency: string
  status: string
  current_period_end: string | null
  canceled_at: string | null
  stripe_subscription_id: string | null
  created_at: string
}

/** The user's subscriptions plus the headline KPIs (active count + MRR). */
export type AssistantSubscriptionListResponse = {
  subscriptions: AssistantSubscription[]
  active_count: number
  mrr_cents: number
}

/** Everything the desktop sidecar needs to render an assistant's video locally. */
export type AiAssistantVideoContext = {
  slug: string
  demo_url: string
  first_name: string | null
  presenter_duration: number
  presenter_intro: number
  presenter_outro: number
  total_seconds: number
  out_width: number
  out_height: number
  fps: number
}

/** Owner edits to an assistant's branding and persona (partial update). */
export type AiAssistantUpdatePayload = {
  assistant_name?: string
  business_name?: string
  languages?: string[]
  tone?: string
  use_brand_color?: boolean
  accent_color?: string
}

/** The assistant customization form state (all fields present for v-model). */
export type AiAssistantEditForm = {
  assistant_name: string
  business_name: string
  tone: string
  accent_color: string
  languages: string[]
}

/** One lead a visitor left through an assistant, as seen by its owner. */
export type AiAssistantLead = {
  id: number
  assistant_id: number
  prospect_id: number | null
  business_name: string
  name: string
  contact: string
  need: string | null
  language: string | null
  created_at: string
}

/** The leads captured across the current user's assistants. */
export type AiAssistantLeadsResponse = {
  leads: AiAssistantLead[]
}
