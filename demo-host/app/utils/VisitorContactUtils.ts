import type { AssistantChatMessage } from '~/types/AiAssistant'
import type { AssistantContactPrefill } from '~/types/AssistantContactPrefill'

// The same rule as the API's VisitorContact: a national number has 9 to 11 digits, an international one
// (« + » or « 00 » first) 10 to 15; a made-up string of digits is refused before the form can be sent.
const MIN_NATIONAL_DIGITS: number = 9
const MAX_NATIONAL_DIGITS: number = 11
const MIN_INTERNATIONAL_DIGITS: number = 10
const MAX_INTERNATIONAL_DIGITS: number = 15
const MAX_NAME_WORDS: number = 3
const MAX_NAME_CHARS: number = 40

/** Prefix, digits and the separators people type between them. */
const PHONE_CHARS: RegExp = /^\+?[\d\s.()/-]+$/
const WHOLE_EMAIL: RegExp = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
const EMAILS_IN_TEXT: RegExp = /[^\s@]+@[^\s@]+\.[^\s@]{2,}/g
/** 8 to 15 digits with separators, « + » or « 00 » before them or not; each match is checked as a phone after. */
const PHONES_IN_TEXT: RegExp = /(?:\+|00)?\d(?:[\s.()/-]*\d){7,14}/g
/** « je m'appelle Léo », « my name is Leo », « Prénom : Léo »… anywhere in the message: the words after it are the name. */
const NAME_OPENINGS: RegExp =
  /(?:^|[\s,;:.!?-])(?:je m['’ ]appelle|moi,? c['’]est|c['’]est|je suis|mon pr[ée]nom(?: est| c['’]est|\s*:)|mon nom(?: est| c['’]est|\s*:)|je me nomme|my name is|my name['’]s|i am|i['’]m|it['’]s|this is|ik ben|ik heet|mijn (?:voor)?naam is|ich bin|ich hei(?:ß|ss)e|mein (?:vor)?name ist|ech sinn|ech heeschen|m[äa]in? (?:vir)?numm ass|pr[ée]nom\s*:|name\s*:|naam\s*:|vorname\s*:)\s*/i
/** The assistant just asked for a name: a short answer without digits is one. */
const NAME_ASKED: RegExp = /pr[ée]nom|\bnom\b|\bname\b|\bnaam\b|\bvorname\b|\bnamen?\b|\bnumm\b/i
const NAME_WORD: RegExp = /^[\p{L}'’-]+$/u
/** Words that never start a name: pronouns, articles, greetings, question words and answers, in the five languages. */
const STOP_WORDS: Set<string> = new Set([
  'je',
  'tu',
  'il',
  'elle',
  'on',
  'nous',
  'vous',
  'ils',
  'elles',
  'me',
  'moi',
  'te',
  'toi',
  'se',
  'le',
  'la',
  'les',
  'un',
  'une',
  'des',
  'du',
  'de',
  'et',
  'ou',
  'ne',
  'pas',
  'non',
  'oui',
  'si',
  'mais',
  'pour',
  'avec',
  'sans',
  'sur',
  'sous',
  'dans',
  'chez',
  'ça',
  'ca',
  'ce',
  'cet',
  'cette',
  'ces',
  'mon',
  'ma',
  'mes',
  'ton',
  'ta',
  'tes',
  'son',
  'sa',
  'ses',
  'votre',
  'vos',
  'notre',
  'nos',
  'merci',
  'bonjour',
  'bonsoir',
  'salut',
  'ok',
  'okay',
  "d'accord",
  'bien',
  'très',
  'tres',
  'plus',
  'moins',
  'combien',
  'comment',
  'quel',
  'quelle',
  'quels',
  'quelles',
  'pourquoi',
  'où',
  'quand',
  'est-ce',
  'peut-être',
  'voilà',
  'voici',
  'aussi',
  'encore',
  'toujours',
  'jamais',
  'rien',
  'tout',
  'tous',
  'toute',
  'toutes',
  'quoi',
  'qui',
  'que',
  'dont',
  'en',
  'y',
  'à',
  'a',
  'au',
  'aux',
  'par',
  'vers',
  'c',
  'i',
  'you',
  'he',
  'she',
  'we',
  'they',
  'my',
  'your',
  'the',
  'an',
  'and',
  'or',
  'not',
  'no',
  'yes',
  'thanks',
  'thank',
  'hello',
  'hi',
  'hey',
  'please',
  'how',
  'what',
  'which',
  'when',
  'where',
  'why',
  'who',
  'it',
  'this',
  'that',
  'is',
  'are',
  'do',
  'does',
  'can',
  'could',
  'would',
  'will',
  'just',
  'also',
  'very',
  'for',
  'with',
  'without',
  'to',
  'of',
  'in',
  'at',
  'ik',
  'jij',
  'u',
  'hij',
  'zij',
  'wij',
  'jullie',
  'mij',
  'mijn',
  'uw',
  'het',
  'een',
  'niet',
  'nee',
  'ja',
  'dank',
  'bedankt',
  'hallo',
  'hoi',
  'hoe',
  'wat',
  'welke',
  'wanneer',
  'waar',
  'waarom',
  'wie',
  'zijn',
  'kan',
  'kunt',
  'ook',
  'voor',
  'met',
  'zonder',
  'naar',
  'van',
  'op',
  'ich',
  'du',
  'er',
  'sie',
  'wir',
  'ihr',
  'mich',
  'mir',
  'mein',
  'meine',
  'ihre',
  'der',
  'die',
  'das',
  'ein',
  'eine',
  'und',
  'oder',
  'nicht',
  'nein',
  'danke',
  'welcher',
  'wann',
  'wo',
  'warum',
  'wer',
  'ist',
  'sind',
  'können',
  'auch',
  'für',
  'mit',
  'ohne',
  'zu',
  'von',
  'auf',
  'bitte',
  'ech',
  'hien',
  'dir',
  'mäin',
  'meng',
  'den',
  'eng',
  'net',
  'jo',
  'moien',
  'äddi',
  'wéi',
  'wéini',
  'wou',
  'firwat',
  'wien',
  'ass',
  'sinn',
  'och',
  'fir',
  'mat',
  'ouni',
  'vun',
])

/**
 * Reads, in what a visitor typed, the phone number or email address the business can reach them at, and the
 * name they gave: the contact form opens already filled with them.
 */
export class VisitorContactUtils {
  /**
   * Whether a contact reads as an email address.
   * @param text - What the visitor typed.
   * @returns True for « nom@domaine.tld », spaces around aside.
   */
  static isEmail(text: string): boolean {
    return WHOLE_EMAIL.test(text.trim())
  }

  /**
   * Whether a contact reads as a phone number the business can dial.
   * @param text - What the visitor typed.
   * @returns True for 9 to 11 digits (national) or 10 to 15 behind « + » or « 00 » (international), any separators
   * between them; false for letters, too few digits or too many.
   */
  static isPhone(text: string): boolean {
    const cleaned: string = text.trim()
    if (!cleaned || !PHONE_CHARS.test(cleaned)) return false
    const digits: string = cleaned.replace(/\D/g, '')
    if (cleaned.startsWith('+') || digits.startsWith('00')) {
      return digits.length >= MIN_INTERNATIONAL_DIGITS && digits.length <= MAX_INTERNATIONAL_DIGITS
    }
    return digits.length >= MIN_NATIONAL_DIGITS && digits.length <= MAX_NATIONAL_DIGITS
  }

  /**
   * Whether the business can reach the visitor with what they typed.
   * @param text - What the visitor typed.
   * @returns True for a phone number or an email address.
   */
  static isReachable(text: string): boolean {
    return VisitorContactUtils.isEmail(text) || VisitorContactUtils.isPhone(text)
  }

  /**
   * The name and contact the visitor gave along the conversation, the most recent of each.
   * @param messages - The thread, visitor and assistant turns.
   * @returns What to prefill; empty strings when the visitor gave nothing yet.
   */
  static extract(messages: AssistantChatMessage[]): AssistantContactPrefill {
    let name: string = ''
    let contact: string = ''
    messages.forEach((message: AssistantChatMessage, index: number): void => {
      if (message.role !== 'user') return
      const found: string | null = VisitorContactUtils.lastContactIn(message.content)
      if (found) contact = found
      const previous: AssistantChatMessage | undefined = messages[index - 1]
      const wasAsked: boolean = previous?.role === 'assistant' && NAME_ASKED.test(previous.content)
      const candidate: string | null = VisitorContactUtils.nameIn(message.content, wasAsked)
      if (candidate) name = candidate
    })
    return { name, contact }
  }

  /**
   * The last email or phone number a message holds.
   * @param text - A visitor's message.
   * @returns The contact, or null.
   */
  private static lastContactIn(text: string): string | null {
    let last: string | null = null
    let lastAt: number = -1
    for (const match of text.matchAll(EMAILS_IN_TEXT)) {
      const at: number = match.index ?? 0
      if (at > lastAt) {
        last = match[0]
        lastAt = at
      }
    }
    for (const match of text.matchAll(PHONES_IN_TEXT)) {
      const phone: string = match[0].trim()
      const at: number = match.index ?? 0
      if (at > lastAt && VisitorContactUtils.isPhone(phone)) {
        last = phone
        lastAt = at
      }
    }
    return last
  }

  /**
   * The name a message gives: after an opening like « je m'appelle », or the message itself when the assistant
   * just asked for the name and the answer is short.
   * @param text - A visitor's message.
   * @param wasAsked - Whether the assistant's previous message asked for a name.
   * @returns The name, each word capitalised, or null.
   */
  private static nameIn(text: string, wasAsked: boolean): string | null {
    const line: string = text.replace(EMAILS_IN_TEXT, ' ').replace(PHONES_IN_TEXT, ' ').trim()
    const opening: RegExpMatchArray | null = line.match(NAME_OPENINGS)
    if (!opening && !wasAsked) return null
    const rest: string = opening ? line.slice((opening.index ?? 0) + opening[0].length) : line
    const tokens: string[] = rest.split(/\s+/).filter((token: string): boolean => token.length > 0)
    // An answer longer than a name (a question, a sentence) is not one.
    if (!opening && tokens.length > MAX_NAME_WORDS) return null
    const words: string[] = []
    for (const token of tokens) {
      const word: string = token.replace(/^[^\p{L}]+|[^\p{L}'’-]+$/gu, '')
      if (!word || !NAME_WORD.test(word) || STOP_WORDS.has(word.toLowerCase())) break
      words.push(VisitorContactUtils.capitalise(word))
      if (/[,.;:!?)]$/.test(token) || words.length === MAX_NAME_WORDS) break
    }
    const name: string = words.join(' ')
    return name && name.length <= MAX_NAME_CHARS ? name : null
  }

  /**
   * A word with its first letter (and the one after each hyphen) in upper case, the rest as typed.
   * @param word - A word of the name.
   * @returns The word capitalised.
   */
  private static capitalise(word: string): string {
    return word
      .split('-')
      .map((part: string): string => part.charAt(0).toLocaleUpperCase() + part.slice(1))
      .join('-')
  }
}
