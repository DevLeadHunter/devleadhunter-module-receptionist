// A tone is stored as prose (« chaleureux, professionnel et concis »): the chips read and write that sentence.
const TONE_SEPARATORS: RegExp = /\s*(?:,|;|\/|\bet\b|&)\s*/i

/**
 * The tone words of an assistant's stored tone, in order, lower case and without duplicates.
 * @param tone - The stored tone sentence, or null.
 * @returns The words (empty when there is no tone).
 */
export function parseAssistantTone(tone: string | null): string[] {
  const words: string[] = []
  for (const raw of (tone ?? '').split(TONE_SEPARATORS)) {
    const word: string = raw.trim().replace(/\.$/, '').toLowerCase()
    if (word && !words.includes(word)) words.push(word)
  }
  return words
}

/**
 * The stored tone sentence for chosen tone words: « chaleureux, professionnel et concis ».
 * @param words - The chosen words, in order.
 * @returns The sentence (empty when nothing is chosen).
 */
export function formatAssistantTone(words: string[]): string {
  if (words.length === 0) return ''
  if (words.length === 1) return words[0] ?? ''
  return `${words.slice(0, -1).join(', ')} et ${words[words.length - 1]}`
}
