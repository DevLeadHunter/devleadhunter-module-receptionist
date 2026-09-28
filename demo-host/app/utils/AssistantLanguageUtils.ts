import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import { LANGUAGE_LABELS } from '~/constants/AssistantWidgetLabels'

/** Codes our own data may still hold for a widget language: Luxembourgish was « lu » before it became BCP 47's « lb ». */
const LEGACY_LANGUAGE_CODES: Map<string, AssistantWidgetLanguage> = new Map([['lu', 'lb']])

const WIDGET_LANGUAGES: Set<string> = new Set(Object.keys(LANGUAGE_LABELS))

/** The widget's languages among an assistant's, and the one a visitor's browser asks for. */
export class AssistantLanguageUtils {
  static readonly DEFAULT_LANGUAGE: AssistantWidgetLanguage = 'fr'

  /**
   * The widget language a browser code asks for (« de-CH » asks for German, « lb-LU » for Luxembourgish).
   * @param code - A BCP 47 tag, as `navigator.languages` or `Accept-Language` give it.
   * @returns The widget language, or null when the widget does not speak it.
   */
  static fromBrowserCode(code: string): AssistantWidgetLanguage | null {
    const primary: string = code.trim().toLowerCase().split(/[-_;]/)[0] ?? ''
    return AssistantLanguageUtils.isWidgetLanguage(primary) ? primary : null
  }

  /**
   * Whether a code is one of the widget's languages, as written.
   * @param code - A lower-case primary language code.
   * @returns True for « fr », « nl », « en », « de » and « lb ».
   */
  static isWidgetLanguage(code: string): code is AssistantWidgetLanguage {
    return WIDGET_LANGUAGES.has(code)
  }

  /**
   * The widget language a code of our own data names, its legacy spelling included (a conversation kept in the
   * browser, an assistant's languages).
   * @param code - The stored code.
   * @returns The widget language, or null when the widget does not speak it.
   */
  static fromStoredCode(code: string | null | undefined): AssistantWidgetLanguage | null {
    const trimmed: string = (code ?? '').trim().toLowerCase()
    return LEGACY_LANGUAGE_CODES.get(trimmed) ?? AssistantLanguageUtils.fromBrowserCode(trimmed)
  }

  /**
   * The widget languages an assistant offers, in its order.
   * @param configured - The assistant's language codes.
   * @returns The ones the widget speaks, each once, or the default language when none is.
   */
  static offered(configured: string[]): AssistantWidgetLanguage[] {
    const languages: AssistantWidgetLanguage[] = []
    for (const code of configured) {
      const language: AssistantWidgetLanguage | null = AssistantLanguageUtils.fromStoredCode(code)
      if (language && !languages.includes(language)) languages.push(language)
    }
    return languages.length ? languages : [AssistantLanguageUtils.DEFAULT_LANGUAGE]
  }

  /**
   * The first of a visitor's languages the assistant offers.
   * @param wanted - The browser's languages, by preference (`navigator.languages`, `Accept-Language`).
   * @param offered - The widget languages the assistant offers.
   * @returns The matching offered language, or null when none matches.
   */
  static firstOffered(wanted: string[], offered: AssistantWidgetLanguage[]): AssistantWidgetLanguage | null {
    for (const code of wanted) {
      const language: AssistantWidgetLanguage | null = AssistantLanguageUtils.fromBrowserCode(code)
      if (language && offered.includes(language)) return language
    }
    return null
  }
}
