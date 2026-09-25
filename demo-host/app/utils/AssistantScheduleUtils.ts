import type { AssistantSlotChoice, AssistantWidgetLang } from '~/types/AiAssistant'
import { APPOINTMENT_LABELS, DATE_LOCALES } from '~/constants/AssistantWidgetLabels'

/** Every targeted country (FR, BE, LU, CH) keeps Paris time: slots always read in the business's time. */
const BUSINESS_TIME_ZONE: string = 'Europe/Paris'

/**
 * Dates and half-days of an appointment, written in the widget's language and the business's time.
 */
export class AssistantScheduleUtils {
  /**
   * A free slot of the agenda (« mar. 22 sept., 10:00 »).
   * @param iso - The slot's start, ISO with its offset.
   * @param lang - The widget's language.
   * @returns The short localized day and time.
   */
  static timeLabel(iso: string, lang: AssistantWidgetLang): string {
    const format: Intl.DateTimeFormat = new Intl.DateTimeFormat(DATE_LOCALES[lang], {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: BUSINESS_TIME_ZONE,
    })
    return format.format(new Date(iso))
  }

  /**
   * A day (« ven. 25 sept. »).
   * @param date - The ISO day.
   * @param lang - The widget's language.
   * @returns The short localized day.
   */
  static dayLabel(date: string, lang: AssistantWidgetLang): string {
    const format: Intl.DateTimeFormat = new Intl.DateTimeFormat(DATE_LOCALES[lang], {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    })
    return format.format(new Date(`${date}T12:00:00`))
  }

  /**
   * A picked half-day, as said in a sentence (« ven. 25 sept., matin »).
   * @param slot - The pick.
   * @param lang - The widget's language.
   * @returns Its label.
   */
  static slotLabel(slot: AssistantSlotChoice, lang: AssistantWidgetLang): string {
    return `${AssistantScheduleUtils.dayLabel(slot.date, lang)}, ${APPOINTMENT_LABELS[lang].periodsInline[slot.period]}`
  }

  /**
   * Several picked half-days on one line (« ven. 25 sept., matin · sam. 26 sept., après-midi »).
   * @param slots - The picks, in order.
   * @param lang - The widget's language.
   * @returns The joined labels, empty when nothing is picked.
   */
  static slotsLine(slots: AssistantSlotChoice[], lang: AssistantWidgetLang): string {
    return slots.map((slot: AssistantSlotChoice): string => AssistantScheduleUtils.slotLabel(slot, lang)).join(' · ')
  }
}
