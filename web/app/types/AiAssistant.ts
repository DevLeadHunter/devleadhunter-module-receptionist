/**
 * An AI assistant generated for a prospect, as seen by its owner. `requests_outside_hours_pct` is the
 * share of the last 30 days' requests received outside the business hours (null when they are unknown);
 * `churn_risk` flags a client subscribed for 30 days whose assistant had no conversation and no request
 * over the last 30. `email` is where the business's alerts, reports and client-space links go.
 */
export type AiAssistantSummary = {
  id: number
  slug: string
  prospect_id: number | null
  business_name: string
  assistant_name: string
  assistant_gender: AiAssistantPersonaGender
  email: string | null
  languages: string[]
  tone: string | null
  accent_color: string | null
  use_brand_color: boolean
  status: string
  demo_url: string
  embed_snippet: string
  demo_link_sent_at: string | null
  expires_at: string | null
  video_status: string | null
  video_page_url: string | null
  video_error: string | null
  subscription_status: string | null
  subscription_amount_cents: number | null
  subscription_interval: string | null
  conversations_7d: number
  conversations_30d: number
  requests_7d: number
  requests_30d: number
  requests_outside_hours_pct: number | null
  churn_risk: boolean
  alerts: AiAssistantAlertSettings
  eu_only: boolean
  created_at: string
}

/**
 * How the business owner is alerted of the requests once the assistant is sold, defaults applied:
 * `phone` in E.164 (null = no SMS), `sms_types` texted at once (the others go by email only), SMS held
 * from `quiet_start_hour` to `quiet_end_hour` (Paris time, equal hours = never held).
 */
export type AiAssistantAlertSettings = {
  phone: string | null
  sms_enabled: boolean
  email_enabled: boolean
  sms_types: AiAssistantRequestType[]
  quiet_start_hour: number
  quiet_end_hour: number
}

/** The current user's assistants. */
export type AiAssistantListResponse = {
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

/**
 * Owner edits to an assistant's branding, persona and alerts (partial update). `alert_phone` and `email` are
 * sent as typed; an empty one clears it.
 */
export type AiAssistantUpdatePayload = {
  assistant_name?: string
  business_name?: string
  languages?: string[]
  tone?: string
  use_brand_color?: boolean
  accent_color?: string
  email?: string
  alert_phone?: string
  alert_sms_enabled?: boolean
  alert_email_enabled?: boolean
  alert_sms_types?: AiAssistantRequestType[]
  alert_quiet_start_hour?: number
  alert_quiet_end_hour?: number
  eu_only?: boolean
}

/** The assistant customization form state (all fields present for v-model). */
export type AiAssistantEditForm = {
  assistant_name: string
  business_name: string
  tone: string
  accent_color: string
  languages: string[]
  email: string
  alert_phone: string
  alert_sms_enabled: boolean
  alert_email_enabled: boolean
  alert_sms_types: AiAssistantRequestType[]
  alert_quiet_start_hour: number
  alert_quiet_end_hour: number
  eu_only: boolean
}

/** What a visitor wants — drives the owner's triage. */
export type AiAssistantRequestType = 'question' | 'quote' | 'appointment' | 'urgent' | 'other'

/** Where the owner is with a request. */
export type AiAssistantRequestStatus = 'new' | 'handled' | 'dropped'

/** Where a request came in. */
export type AiAssistantRequestChannel = 'site' | 'email' | 'photo'

/**
 * A request a visitor left through an assistant, typed and summarized for the owner; `appointment_slots` are the
 * wished half-days of an appointment request, in French (« lun. 28/09, matin »), and `appointment_booked` the
 * appointment booked in the client's agenda (« mar. 29/09 à 14:30 (Révision) »).
 */
export type AiAssistantRequestItem = {
  id: number
  assistant_id: number
  prospect_id: number | null
  business_name: string
  type: AiAssistantRequestType
  status: AiAssistantRequestStatus
  channel: AiAssistantRequestChannel
  name: string
  contact: string
  need: string | null
  need_summary: string | null
  language: string | null
  received_outside_hours: boolean | null
  is_test: boolean
  owner_note: string | null
  photo_urls: string[]
  appointment_slots: string[]
  appointment_booked: string | null
  created_at: string
  handled_at: string | null
}

/** The user's requests across their assistants, newest first. */
export type AiAssistantRequestsResponse = {
  requests: AiAssistantRequestItem[]
  pending_count: number
}

/** Owner changes to a request (partial). */
export type AiAssistantRequestUpdatePayload = {
  status?: AiAssistantRequestStatus
  owner_note?: string
}

/** One turn of the conversation a request came out of. */
export type AiAssistantTranscriptLine = {
  role: 'user' | 'assistant'
  content: string
}

/** A request with the conversation that led to it. */
export type AiAssistantRequestDetail = {
  request: AiAssistantRequestItem
  transcript: AiAssistantTranscriptLine[]
}

/** One turn of a journaled conversation. */
export type AiAssistantConversationMessage = {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

/** One visitor conversation with an assistant, as the owner reads it. */
export type AiAssistantConversation = {
  id: number
  session_id: string
  language: string | null
  message_count: number
  started_at: string
  last_message_at: string
  messages: AiAssistantConversationMessage[]
}

/** The latest conversations of one assistant, newest first. */
export type AiAssistantConversationsResponse = {
  assistant_id: number
  business_name: string
  conversations: AiAssistantConversation[]
}

/** A fresh client-space link of a sold assistant; `sent_to` is the address it was emailed to, if any. */
export type AiAssistantClientLink = {
  url: string
  expires_at: string
  sent_to: string | null
  send_error: string | null
}

/** Grammatical gender a persona speaks in, as the API resolves it from the first name. */
export type AiAssistantPersonaGender = 'feminine' | 'masculine'

/** One receptionist of the casting: a first name, the slug of its portrait on the demo host, and its gender. */
export type AiAssistantPersona = {
  name: string
  slug: string
  gender: AiAssistantPersonaGender
}
