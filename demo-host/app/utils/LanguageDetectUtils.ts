import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { LanguageMarkerHits } from '~/types/LanguageDetect'

/**
 * Words that give a language away, each list free of the others' words (« de » is French and Dutch, so it is in
 * neither). Short messages carry few of them: the guess only lands when it is clear.
 */
const MARKERS: Record<AssistantWidgetLanguage, string[]> = {
  fr: [
    'je',
    'vous',
    'nous',
    'le',
    'la',
    'les',
    'une',
    'est',
    'sont',
    'avez',
    'pouvez',
    'merci',
    'bonjour',
    'pour',
    'avec',
    'quel',
    'quelle',
    'quels',
    'comment',
    'mon',
    'ma',
    'mes',
    'votre',
    'vos',
    'faites',
    'des',
    'du',
    'et',
    'pas',
    'sur',
    'dans',
    'ai',
    'suis',
    'voudrais',
    'rendez',
    'devis',
    'cette',
    'ce',
    'ça',
    'oui',
  ],
  nl: [
    'ik',
    'wij',
    'jullie',
    'niet',
    'het',
    'een',
    'zijn',
    'hebben',
    'heb',
    'kunnen',
    'kunt',
    'graag',
    'voor',
    'van',
    'met',
    'wat',
    'hoe',
    'mijn',
    'uw',
    'dank',
    'bedankt',
    'hallo',
    'goedemorgen',
    'offerte',
    'afspraak',
    'ja',
    'nee',
    'ook',
    'maar',
  ],
  en: [
    'i',
    'you',
    'we',
    'the',
    'is',
    'are',
    'have',
    'can',
    'could',
    'would',
    'please',
    'thanks',
    'thank',
    'hello',
    'hi',
    'like',
    'for',
    'with',
    'what',
    'how',
    'do',
    'does',
    'my',
    'your',
    'quote',
    'appointment',
    'need',
    'want',
    'yes',
    'and',
  ],
  de: [
    'ich',
    'sie',
    'wir',
    'nicht',
    'ist',
    'sind',
    'und',
    'der',
    'die',
    'das',
    'haben',
    'habe',
    'können',
    'bitte',
    'danke',
    'hallo',
    'möchte',
    'für',
    'mit',
    'was',
    'wie',
    'mein',
    'meine',
    'ihr',
    'ihre',
    'angebot',
    'termin',
    'brauche',
    'ja',
    'auch',
  ],
  lb: [
    'ech',
    'dir',
    'mir',
    'net',
    'ass',
    'sinn',
    'wéi',
    'mat',
    'fir',
    'den',
    'hunn',
    'kann',
    'kënnt',
    'wëll',
    'moien',
    'merci',
    'wat',
    'mäin',
    'meng',
    'äre',
    'är',
    'devis',
    'rendez',
    'jo',
    'och',
    'awer',
  ],
}

/** Fewer words than this: too little to tell. */
const MIN_WORDS: number = 3
/** A language needs this many of its markers, and more than any other, to be picked. */
const MIN_HITS: number = 2

/**
 * Guesses the language a visitor writes in, so the widget's own labels follow them, without any network call.
 */
export class LanguageDetectUtils {
  /**
   * The language a text is written in, among the ones the widget offers.
   * @param text - The visitor's message, or the assistant's reply.
   * @param offered - The languages the widget offers.
   * @returns The clear winner, or null when the text is too short or ambiguous (the widget then keeps its language).
   */
  static detect(text: string, offered: AssistantWidgetLanguage[]): AssistantWidgetLanguage | null {
    const words: string[] = text
      .toLowerCase()
      .split(/[^\p{L}]+/u)
      .filter((word: string): boolean => word.length > 0)
    if (words.length < MIN_WORDS) return null
    const ranking: LanguageMarkerHits[] = offered
      .map((language: AssistantWidgetLanguage): LanguageMarkerHits => {
        const markers: Set<string> = new Set(MARKERS[language])
        return { language, hits: words.filter((word: string): boolean => markers.has(word)).length }
      })
      .sort((first: LanguageMarkerHits, second: LanguageMarkerHits): number => second.hits - first.hits)
    const best: LanguageMarkerHits | undefined = ranking[0]
    const runnerUpHits: number = ranking[1]?.hits ?? 0
    if (!best || best.hits < MIN_HITS || best.hits <= runnerUpHits) return null
    return best.language
  }
}
