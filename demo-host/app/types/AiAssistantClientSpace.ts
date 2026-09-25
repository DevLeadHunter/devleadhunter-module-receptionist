import type { AssistantWidgetLang } from '~/types/AiAssistant'

/** What a visitor asked for, as the API types a request. */
export type AiAssistantClientRequestType = 'question' | 'quote' | 'appointment' | 'urgent' | 'other'

/** Where the business is with a request. */
export type AiAssistantClientRequestStatus = 'new' | 'handled' | 'dropped'

/**
 * One request as its client sees it; `received_label` is already in business time (« 14/09 à 10:05 »),
 * `appointment_slots` are the wished half-days of an appointment request (« lun. 28/09, matin »), to confirm,
 * and `appointment_booked` the appointment already in the agenda (« mar. 29/09 à 14:30 (Révision) »).
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
  appointment_booked: string | null
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
  /** The request types texted at once; the others go by email only. */
  alert_sms_types: AiAssistantClientRequestType[]
  /** The window during which the SMS are held (Paris hours; equal hours = never held). */
  alert_quiet_start_hour: number
  alert_quiet_end_hour: number
}

/** A language the widget can speak, with its French name. */
export type AiAssistantClientLanguageOption = {
  code: AssistantWidgetLang
  label: string
}

/** Where the agenda stands: Google not configured on the server, not connected, connected, or its access lost. */
export type AiAssistantClientCalendarStatus = 'unavailable' | 'disconnected' | 'connected' | 'error'

/**
 * The agenda section: its connection, the booking settings (defaults applied), the choices offered, and the last
 * problem met with the agenda (`last_error`, cleared by a booking).
 */
export type AiAssistantClientCalendar = {
  status: AiAssistantClientCalendarStatus
  account_email: string | null
  calendar_id: string
  duration_minutes: number
  min_notice_hours: number
  appointment_types: string[]
  last_error: string | null
  duration_choices: number[]
  min_notice_choices: number[]
}

/** A client's booking settings edit; every field is optional. */
export type AiAssistantClientCalendarUpdate = Partial<
  Pick<AiAssistantClientCalendar, 'calendar_id' | 'duration_minutes' | 'min_notice_hours' | 'appointment_types'>
>

/** The Google consent page to open in a new tab. */
export type AiAssistantClientCalendarConnect = {
  url: string
}

/** An upcoming appointment the assistant booked; `start_label` is in business time (« mar. 29/09 à 14:30 »). */
export type AiAssistantClientAppointment = {
  id: number
  start_label: string
  type_label: string | null
  name: string
  contact: string
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
  /** The example space a prospect opens from its demo page: fictional data, nothing to save. */
  is_example: boolean
  settings: AiAssistantClientSettings
  language_options: AiAssistantClientLanguageOption[]
  subscription: AiAssistantClientSubscription | null
  calendar: AiAssistantClientCalendar
  appointments: AiAssistantClientAppointment[]
  faq: AiAssistantClientFaqEntry[]
  unanswered: AiAssistantClientUnansweredEntry[]
}

/** A question the receptionist could not answer, with how often visitors asked it (dates in naive UTC). */
export type AiAssistantClientUnansweredEntry = {
  question: string
  count: number
  first_seen: string | null
  last_seen: string | null
}

/** An answer the business gave, which the receptionist now uses as is. */
export type AiAssistantClientFaqEntry = {
  question: string
  answer: string
  created_at: string | null
}

/** The two lists, as the API returns them after a change. */
export type AiAssistantClientFaqResponse = {
  faq: AiAssistantClientFaqEntry[]
  unanswered: AiAssistantClientUnansweredEntry[]
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
