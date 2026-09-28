import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import { LANGUAGE_LABELS } from '~/constants/AssistantWidgetLabels'

/** The widget's languages among an assistant's, and the one a visitor's browser asks for. */
export class AssistantLanguageUtils {
  static readonly DEFAULT_LANGUAGE: AssistantWidgetLanguage = 'fr'

  /**
   * The widget languages an assistant offers, in its order.
   * @param configured - The assistant's language codes.
   * @returns The ones the widget speaks, or the default language when none is.
   */
  static offered(configured: string[]): AssistantWidgetLanguage[] {
    const languages: AssistantWidgetLanguage[] = configured.filter(
      (code: string): code is AssistantWidgetLanguage => code in LANGUAGE_LABELS,
    )
    return languages.length ? languages : [AssistantLanguageUtils.DEFAULT_LANGUAGE]
  }

  /**
   * The first of a visitor's languages the assistant offers (« de-CH » asks for German).
   * @param wanted - The browser's languages, by preference (`navigator.languages`, `Accept-Language`).
   * @param offered - The widget languages the assistant offers.
   * @returns The matching offered language, or null when none matches.
   */
  static firstOffered(wanted: string[], offered: AssistantWidgetLanguage[]): AssistantWidgetLanguage | null {
    for (const code of wanted) {
      const primary: string = code.trim().slice(0, 2).toLowerCase()
      const match: AssistantWidgetLanguage | undefined = offered.find(
        (language: AssistantWidgetLanguage): boolean => language === primary,
      )
      if (match) return match
    }
    return null
  }
}
