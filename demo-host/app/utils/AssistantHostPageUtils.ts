import type { AssistantGreetingContext, AssistantHostPage } from '~/types/AssistantDemoScript'

/** Words of a contact page, in the widget's languages, folded. */
const CONTACT_WORDS: RegExp = /contact|kontakt|nous-joindre|joindre|reach-us/

/** Words of a quote or pricing page. */
const QUOTE_WORDS: RegExp = /devis|tarif|prix|offerte|prijs|angebot|preis|quote|pricing|estimate/

/** Words of an appointment or booking page. */
const APPOINTMENT_WORDS: RegExp = /rendez|rdv|afspraak|termin|appointment|booking|reserv/

/** What the page a widget sits on is about, read off its path and title. */
export class AssistantHostPageUtils {
  /**
   * The context the greeting adapts to.
   * @param page - The host page as the loader reported it, or null on our own pages.
   * @returns The context, `default` when the page says nothing in particular.
   */
  static context(page: AssistantHostPage | null): AssistantGreetingContext {
    if (!page) return 'default'
    const text: string = AssistantHostPageUtils.fold(`${page.path} ${page.title}`)
    if (APPOINTMENT_WORDS.test(text)) return 'appointment'
    if (QUOTE_WORDS.test(text)) return 'quote'
    if (CONTACT_WORDS.test(text)) return 'contact'
    return 'default'
  }

  /**
   * Lower-case text without accents.
   * @param value - The text.
   * @returns The folded text.
   */
  private static fold(value: string): string {
    return value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
  }
}
