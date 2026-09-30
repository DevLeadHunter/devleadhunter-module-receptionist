import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantSuggestionAction } from '~/types/AssistantChat'
import { APPOINTMENT_LABELS, LEAD_LABELS, PHOTO_LABELS } from '~/constants/AssistantWidgetLabels'

/** Other wordings the model gives the widget's three actions, beside the widget's own labels. */
const OTHER_ACTION_WORDINGS: Record<AssistantSuggestionAction, string[]> = {
  callback: [
    'Me faire rappeler',
    'Rappelez-moi',
    'Être recontacté',
    'Laisser mes coordonnées',
    'Donner mes coordonnées',
    'Donner coordonnées',
    'Donner mon numéro',
    'Laisser mon numéro',
    'Call me back',
    'Get a call back',
    'Leave my details',
    'Bel me terug',
    'Rufen Sie mich zurück',
  ],
  appointment: ['Prendre un rendez-vous', 'Réserver un créneau', 'Make an appointment', 'Een afspraak maken'],
  photo: ['Envoyer une photo', 'Je vous envoie une photo', 'Send a photo', 'Een foto sturen', 'Ein Foto senden'],
}

/**
 * A chip's words, accent-free and lower case, without the closing punctuation.
 * @param text - The chip's text.
 * @returns The words to compare.
 */
function comparableWords(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[.!?…]+$/u, '')
    .replace(/\s+/g, ' ')
    .trim()
}

const WIDGET_LANGUAGES: AssistantWidgetLanguage[] = Object.keys(LEAD_LABELS) as AssistantWidgetLanguage[]

/** Each action's wordings, in every widget language, ready to compare. */
const ACTION_WORDINGS: Record<AssistantSuggestionAction, Set<string>> = {
  callback: new Set(
    [
      ...WIDGET_LANGUAGES.map((language: AssistantWidgetLanguage): string => LEAD_LABELS[language].open),
      ...OTHER_ACTION_WORDINGS.callback,
    ].map(comparableWords),
  ),
  appointment: new Set(
    [
      ...WIDGET_LANGUAGES.flatMap((language: AssistantWidgetLanguage): string[] => [
        APPOINTMENT_LABELS[language].chip,
        APPOINTMENT_LABELS[language].button,
      ]),
      ...OTHER_ACTION_WORDINGS.appointment,
    ].map(comparableWords),
  ),
  photo: new Set(
    [
      ...WIDGET_LANGUAGES.flatMap((language: AssistantWidgetLanguage): string[] => [
        PHOTO_LABELS[language].chip,
        PHOTO_LABELS[language].button,
      ]),
      ...OTHER_ACTION_WORDINGS.photo,
    ].map(comparableWords),
  ),
}

/** Reads the suggestion chips the model offers. */
export class AssistantSuggestionUtils {
  /**
   * The widget action a suggestion chip names, when it names one.
   * @param text - The chip's text.
   * @returns The action, or null for a question to send as the visitor's message.
   */
  static actionOf(text: string): AssistantSuggestionAction | null {
    const words: string = comparableWords(text)
    const actions: AssistantSuggestionAction[] = Object.keys(ACTION_WORDINGS) as AssistantSuggestionAction[]
    return actions.find((action: AssistantSuggestionAction): boolean => ACTION_WORDINGS[action].has(words)) ?? null
  }

  /**
   * The chips, with one at most per widget action.
   * @param chips - The chips the model offers.
   * @returns The chips, the later ones naming an action already offered left out.
   */
  static onePerAction(chips: string[]): string[] {
    const offeredActions: Set<AssistantSuggestionAction> = new Set()
    return chips.filter((chip: string): boolean => {
      const action: AssistantSuggestionAction | null = AssistantSuggestionUtils.actionOf(chip)
      if (action === null) return true
      if (offeredActions.has(action)) return false
      offeredActions.add(action)
      return true
    })
  }
}
