/** Grammatical gender the persona speaks in, resolved by the API from its first name. */
export type AiAssistantPersonaGender = 'feminine' | 'masculine'

/** One receptionist of the casting: a first name, the slug of its portrait file, and its gender. */
export type AiAssistantPersona = {
  name: string
  slug: string
  gender: AiAssistantPersonaGender
}

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
export type AiAssistantConfig = {
  slug: string
  business_name: string
  assistant_name: string
  assistant_gender?: AiAssistantPersonaGender
  languages: string[]
  accent_color: string | null
  status: string
  city?: string | null
  trade_label?: string | null
  google_rating?: number | null
  google_reviews_count?: number | null
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

/**
 * A single conversation turn exchanged with the assistant; `follow_ups` on a reply are the questions it offers the
 * visitor to ask next (chips under it while it is the last message).
 */
export type AssistantChatMessage = {
  role: 'user' | 'assistant'
  content: string
  follow_ups?: string[]
}

/** A line of the widget's thread; an `isLocal` one is the widget's own, never stored nor sent to the model. */
export type AssistantThreadMessage = AssistantChatMessage & {
  isLocal?: boolean
}

/** The phone number or email a visitor typed in the chat, filed by the API as their request. */
export type AssistantCapturedContact = {
  name: string
  contact: string
}

/**
 * The assistant's reply to a chat request; `offer_booking` when the visitor asks for an appointment, `follow_ups`
 * the questions offered next, `daily_limit_reached` when it answered its messages of the day (a fixed reply).
 */
export type AssistantChatReply = {
  reply: string
  offer_booking: boolean
  follow_ups: string[]
  daily_limit_reached: boolean
  captured_contact: AssistantCapturedContact | null
}

/** Localized labels for the lead-capture form; `contactHint` shows under a contact that cannot be reached. */
export type AssistantLeadLabels = {
  open: string
  title: string
  name: string
  contactBy: string
  phone: string
  email: string
  contactHint: string
  need: string
  send: string
  cancel: string
  sent: string
}

/** How the visitor wants to be reached: the contact field's keyboard and autofill follow it. */
export type AssistantContactChannel = 'phone' | 'email'

/** What the visitor reads when a call fails; `unavailable` carries `{name}` and `{business}`. */
export type AssistantErrorLabels = {
  rateLimited: string
  network: string
  server: string
  unavailable: string
}

/** The codes of a pick the API refused, read by the widget rather than its sentence. */
export type AssistantSlotRefusalCode = 'slot_taken' | 'slot_withdrawn'

/** Languages the widget offers preset greetings and suggestions for (Luxembourgish is BCP 47's « lb »). */
export type AssistantWidgetLanguage = 'fr' | 'nl' | 'en' | 'de' | 'lb'

/** @deprecated Use `AssistantWidgetLanguage`: kept while the client space still imports this name. */
export type AssistantWidgetLang = AssistantWidgetLanguage

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
  /** Replaces « photo sent » in the thread when the API refused the photo. */
  refused: string
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

/** A free slot of the agenda the visitor picked, and its kind. */
export type AssistantBookingChoice = {
  start: string
  type: string | null
}

/** The visitor's details as the widget sends them: they become a request, with the appointment picked. */
export type AssistantLeadRequestBody = {
  name: string
  contact: string
  need: string
  language: AssistantWidgetLanguage
  session_id: string
  internal: boolean
  slots: AssistantSlotChoice[]
  booking: AssistantBookingChoice | null
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

/** The widget's chrome wording in one language; `open` carries `{name}`. */
export type AssistantUiLabels = {
  close: string
  open: string
  launcherBefore: string
  launcherAfter: string
  typing: string
  language: string
  message: string
  send: string
  /** The « + » of a narrow bar, which unfolds the photo and appointment actions. */
  more: string
}

/**
 * The conversation the demo page plays by itself in one language: the chip that starts it, the visitor's opening,
 * the reply asking for a photo and the closing reply (`{business}` in both).
 */
export type AssistantExampleLabels = {
  chip: string
  visitor: string
  askPhoto: string
  thanks: string
}

/**
 * What the widget sends to be answered: the recent thread, the visitor's session and language, and the name they gave
 * in it (it names the request a phone number typed in the chat opens).
 */
export type AssistantChatRequestBody = {
  messages: AssistantChatMessage[]
  session_id: string
  language: AssistantWidgetLanguage
  internal: boolean
  visitor_name?: string
}

/** One frame of the streamed reply: a piece of text, then the closing frame with the whole reply. */
export type AssistantChatStreamFrame = {
  delta?: string
  done?: boolean
  reply?: string
  offer_booking?: boolean
  follow_ups?: string[]
  daily_limit_reached?: boolean
  captured_contact?: AssistantCapturedContact | null
}
