import type { AssistantWidgetLang } from '~/types/AiAssistant'

/** What a visitor asked for, as the API types a request. */
export type AiAssistantClientRequestType = 'question' | 'quote' | 'appointment' | 'urgent' | 'other'

/** Where the business is with a request. */
export type AiAssistantClientRequestStatus = 'new' | 'handled' | 'dropped'

/**
 * One request as its client sees it; `received_label` is already in business time (« 14/09 à 10:05 ») and
 * `appointment_slots` are the wished half-days of an appointment request (« lun. 28/09, matin »), to confirm.
 */
export type AiAssistantClientRequest = {
  id: number
  type: AiAssistantClientRequestType
  status: AiAssistantClientRequestStatus
  name: string
  contact: string
  summary: string | null
  received_label: string
  received_outside_hours: boolean | null
  photo_urls: string[]
  appointment_slots: string[]
}

/** The latest monthly report of the assistant; its sentences come ready-made, like in the report email. */
export type AiAssistantClientReport = {
  month_label: string
  conversations: number
  requests: number
  quotes: number
  appointments: number
  urgent: number
  photo_requests: number
  outside_hours_pct: number | null
  languages_line: string | null
  handling_line: string | null
  top_questions: string[]
}

/** Where the client's subscription stands. */
export type AiAssistantClientSubscriptionStatus = 'incomplete' | 'active' | 'past_due' | 'canceled'

/**
 * The client's subscription; `cancel_scheduled` means paid until the period end but not renewed, and
 * `can_manage` tells whether the Stripe billing portal can open.
 */
export type AiAssistantClientSubscription = {
  status: AiAssistantClientSubscriptionStatus
  price_label: string
  period_end_label: string | null
  cancel_scheduled: boolean
  can_manage: boolean
}

/** The settings a client may change, defaults applied. */
export type AiAssistantClientSettings = {
  assistant_name: string
  languages: AssistantWidgetLang[]
  alert_phone: string | null
  alert_sms_enabled: boolean
  alert_email_enabled: boolean
}

/** A language the widget can speak, with its French name. */
export type AiAssistantClientLanguageOption = {
  code: AssistantWidgetLang
  label: string
}

/** Everything the client-space page shows, as served by the API. */
export type AiAssistantClientSpace = {
  business_name: string
  assistant_name: string
  accent_color: string | null
  link_expires_label: string
  pending_count: number
  requests: AiAssistantClientRequest[]
  report: AiAssistantClientReport | null
  settings: AiAssistantClientSettings
  language_options: AiAssistantClientLanguageOption[]
  subscription: AiAssistantClientSubscription | null
}

/** A client's settings edit; every field is optional. */
export type AiAssistantClientSettingsUpdate = Partial<AiAssistantClientSettings>

/** Where the page stands: loading, the space, an expired link (a new one can be emailed), an unknown link, or an outage. */
export type AiAssistantClientSpaceState = 'loading' | 'ready' | 'expired' | 'invalid' | 'unavailable'

/** The page's load result: its state, and the space when it opened. */
export type AiAssistantClientSpaceLoad = {
  state: AiAssistantClientSpaceState
  space: AiAssistantClientSpace | null
}

/** The Stripe billing portal session to open. */
export type AiAssistantClientPortal = {
  url: string
}

/** Whether a fresh link was emailed to the business. */
export type AiAssistantClientRenew = {
  sent: boolean
}

/** Where the « recevoir un nouveau lien » request of an expired link stands. */
export type AiAssistantClientRenewState = 'idle' | 'sending' | 'sent' | 'failed'
