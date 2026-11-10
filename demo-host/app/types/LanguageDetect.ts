import type { AssistantWidgetLanguage } from './AiAssistant'

/** How many of a language's marker words a text holds. */
export type LanguageMarkerHits = {
  language: AssistantWidgetLanguage
  hits: number
}
