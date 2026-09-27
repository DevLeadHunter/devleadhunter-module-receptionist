/** One day of the business's hours, as its Google listing words it (« lundi », « 08:00–12:00, 14:00–18:00 »). */
export type AiAssistantOpeningHoursRow = {
  day: string
  hours: string
  is_today: boolean
}

/** The business on a sold receptionist's page: how its customers reach it, and when. */
export type AiAssistantPublicBusiness = {
  phone: string | null
  address: string | null
  opening_hours: AiAssistantOpeningHoursRow[]
}
