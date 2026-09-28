/** One day of the business's hours, as its Google listing words it (« lundi », « 08:00–12:00, 14:00–18:00 »). */
export type AiAssistantOpeningHoursRow = {
  day: string
  hours: string
  is_today: boolean
}

/** The business: how its customers reach it, when, and how Google rates it. */
export type AiAssistantPublicBusiness = {
  phone: string | null
  address: string | null
  opening_hours: AiAssistantOpeningHoursRow[]
  is_open_now: boolean | null
  google_rating: number | null
  google_reviews_count: number | null
}
