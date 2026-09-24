/** Grammatical gender the persona speaks in, resolved by the API from its first name. */
export type AiAssistantPersonaGender = 'feminine' | 'masculine'

/**
 * The demo page's estimate: how long the business is closed from 7:00 to 22:00 (its Google hours), over a week and
 * over `month` (1 to 12), and the requests that would come in meanwhile, on a base of `monthly_requests` for its
 * trade (« un plombier »).
 */
export type AiAssistantClosedHours = {
  open_hours_per_week: number
  closed_share_pct: number
  closed_hours_in_month: number
  month: number
  trade_label: string
  monthly_requests: number
  estimated_requests: number
}

/** Public configuration of a prospect's AI assistant, served by the API and consumed as-is. */
export interface AiAssistantConfig {
  slug: string
  business_name: string
  assistant_name: string
  assistant_gender?: AiAssistantPersonaGender
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
  monthly_price_label?: string | null
  closed_hours?: AiAssistantClosedHours | null
}

/** A single conversation turn exchanged with the assistant. */
export interface AssistantChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/** The assistant's reply to a chat request; `offer_booking` when the visitor asks for an appointment. */
export interface AssistantChatReply {
  reply: string
  offer_booking: boolean
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

/** The assistant's answer to a photo sent for a quote. */
export type AssistantPhotoReply = {
  accepted: boolean
  reply: string
  need: string | null
  remaining: number
}

/** Localized texts of the photo chip and button, their privacy note and their errors. */
export type AssistantPhotoLabels = {
  chip: string
  button: string
  note: string
  pick: string
  sent: string
  invalid: string
  tooLarge: string
  quota: string
}

/** A half-day of an appointment request. */
export type AssistantDayPeriod = 'morning' | 'afternoon'

/** An open day (ISO date, the business's day) and the half-days a visitor may pick in it. */
export type AssistantAppointmentDay = {
  date: string
  periods: AssistantDayPeriod[]
}

/** How the widget takes an appointment: booked in the business's agenda, or half-days the business confirms. */
export type AssistantBookingMode = 'calendar' | 'request'

/** A free slot of the business's agenda (ISO moments with their offset). */
export type AssistantAppointmentTime = {
  start: string
  end: string
}

/**
 * What the appointment panel offers: free slots of the agenda (`calendar`, three at a time, `types` to pick
 * from) or open half-days (`request`, `max_chosen` of them).
 */
export type AssistantAppointmentSlots = {
  mode: AssistantBookingMode
  days: AssistantAppointmentDay[]
  max_chosen: number
  times: AssistantAppointmentTime[]
  has_more: boolean
  types: string[]
  duration_minutes: number | null
}

/**
 * The API's answer to a request; `booked_start` when the appointment was booked in the agenda, and how the
 * visitor gets its confirmation (none without a mobile of the served countries nor an email).
 */
export type AssistantLeadReply = {
  ok: boolean
  booked_start: string | null
  confirmation_channel: 'sms' | 'email' | null
}

/** A half-day the visitor picked. */
export type AssistantSlotChoice = {
  date: string
  period: AssistantDayPeriod
}

/** Where the slot panel's data stands. */
export type AssistantSlotsState = 'idle' | 'loading' | 'ready' | 'error'

/**
 * Localized texts of the appointment chip, button and slot panel. `periods` label the buttons, `periodsInline`
 * the half-days inside a sentence; `sent` and `booked` carry a `{slots}` placeholder, `bookedSms` / `bookedEmail`
 * follow `booked` when a confirmation leaves.
 */
export type AssistantAppointmentLabels = {
  chip: string
  button: string
  title: string
  titleCalendar: string
  kind: string
  more: string
  appointment: string
  booked: string
  bookedSms: string
  bookedEmail: string
  first: string
  taken: string
  periods: Record<AssistantDayPeriod, string>
  periodsInline: Record<AssistantDayPeriod, string>
  next: string
  loading: string
  none: string
  error: string
  chosen: string
  unavailable: string
  sent: string
}
