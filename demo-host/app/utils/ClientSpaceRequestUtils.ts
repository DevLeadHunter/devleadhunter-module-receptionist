import type { AiAssistantClientRequest, AiAssistantClientRequestType } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceRequestDayGroup, ClientSpaceRequestStatus } from '~/types/ClientSpaceRequestList'

/** What a visitor asked for, as the client reads it. */
const TYPE_LABELS: Record<AiAssistantClientRequestType, string> = {
  question: 'Question',
  quote: 'Devis',
  appointment: 'Rendez-vous',
  urgent: 'Urgence',
  other: 'Demande',
}

/** The day label's format (« lundi 21 septembre »). */
const DAY_FORMAT: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
})

/** How the client space reads a request: its initials, its status, its day. */
export class ClientSpaceRequestUtils {
  /**
   * The visitor's initials for the avatar disc (« KB »), one letter for a single word, « ? » when unnamed.
   * @param name - The visitor's name.
   * @returns One or two upper-case letters.
   */
  static initials(name: string): string {
    const words: string[] = name
      .trim()
      .split(/[\s-]+/)
      .filter((word: string): boolean => word.length > 0)
    if (words.length === 0) return '?'
    const first: string = words[0]?.charAt(0) ?? ''
    const last: string = words.length > 1 ? (words[words.length - 1]?.charAt(0) ?? '') : ''
    return (first + last).toUpperCase()
  }

  /**
   * What a request is, as the client reads it.
   * @param type - The request type.
   * @returns Its label.
   */
  static typeLabel(type: AiAssistantClientRequestType): string {
    return TYPE_LABELS[type]
  }

  /**
   * The short status shown at the right of a request: what it is while it waits, what became of it afterwards.
   * @param request - The request.
   * @returns The status label and its tone.
   */
  static status(request: AiAssistantClientRequest): ClientSpaceRequestStatus {
    if (request.status === 'handled') return { label: 'Rappelée', tone: 'grey' }
    if (request.status === 'dropped') return { label: 'Sans suite', tone: 'grey' }
    if (request.appointment_booked) return { label: 'RDV pris', tone: 'green' }
    if (request.type === 'urgent') return { label: 'Urgent', tone: 'red' }
    return { label: TYPE_LABELS[request.type], tone: 'accent' }
  }

  /**
   * A business-time day as the list titles it: « Aujourd'hui », « Hier », else « lundi 21 septembre ».
   * @param day - The day, « 2026-09-21 » (empty when the API predates it).
   * @param today - Today, in the same form (tests); the visitor's today otherwise.
   * @returns The title.
   */
  static dayLabel(day: string, today: string = ClientSpaceRequestUtils.today()): string {
    if (!day) return 'Plus tôt'
    if (day === today) return "Aujourd'hui"
    if (day === ClientSpaceRequestUtils.shift(today, -1)) return 'Hier'
    const [year, month, date]: number[] = day.split('-').map(Number)
    const label: string = DAY_FORMAT.format(new Date(year ?? 1970, (month ?? 1) - 1, date ?? 1))
    return label.charAt(0).toUpperCase() + label.slice(1)
  }

  /**
   * The requests grouped by their business-time day, in the order given (newest first).
   * @param requests - The requests.
   * @returns The groups, each titled.
   */
  static groupByDay(requests: AiAssistantClientRequest[]): ClientSpaceRequestDayGroup[] {
    const groups: ClientSpaceRequestDayGroup[] = []
    for (const request of requests) {
      const day: string = request.received_day ?? ''
      const last: ClientSpaceRequestDayGroup | undefined = groups[groups.length - 1]
      if (last && last.day === day) last.requests.push(request)
      else groups.push({ day, label: ClientSpaceRequestUtils.dayLabel(day), requests: [request] })
    }
    return groups
  }

  /**
   * Today in the visitor's time zone, « 2026-09-27 ».
   * @returns The ISO day.
   */
  private static today(): string {
    return ClientSpaceRequestUtils.iso(new Date())
  }

  /**
   * A day moved by some days.
   * @param day - The day, « 2026-09-27 ».
   * @param days - How many days to add (negative to go back).
   * @returns The ISO day.
   */
  private static shift(day: string, days: number): string {
    const [year, month, date]: number[] = day.split('-').map(Number)
    const moved: Date = new Date(year ?? 1970, (month ?? 1) - 1, (date ?? 1) + days)
    return ClientSpaceRequestUtils.iso(moved)
  }

  /**
   * A local date as an ISO day.
   * @param date - The date.
   * @returns « 2026-09-27 ».
   */
  private static iso(date: Date): string {
    const month: string = String(date.getMonth() + 1).padStart(2, '0')
    const day: string = String(date.getDate()).padStart(2, '0')
    return `${date.getFullYear()}-${month}-${day}`
  }
}
