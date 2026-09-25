import type { AiAssistantPersona, AiAssistantPersonaGender } from '~/types/AiAssistant'
import { ASSISTANT_CASTING, ASSISTANT_DEFAULT_PERSONA } from '~/constants/assistantCasting'

/**
 * The origin of the demo host serving the portraits, read off a demo link.
 * @param demoUrl - The assistant's demo link.
 * @returns The origin, or an empty string when the link is not a URL.
 */
export function portraitOrigin(demoUrl: string): string {
  try {
    return new URL(demoUrl).origin
  } catch {
    return ''
  }
}

/**
 * A first name as the file name of its portrait (« Léa » → `lea`).
 * @param name - The first name.
 * @returns The slug.
 */
function personaSlug(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

/**
 * A small stable number for a text, to pick the same face for the same name every time.
 * @param value - The text.
 * @returns A non-negative integer.
 */
function stableHash(value: string): number {
  let hash: number = 0
  for (const character of value) hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  return hash
}

/**
 * The casting persona whose face a first name takes, as the demo host resolves it: its own when the name is in the
 * casting, else one of the same gender picked from the name, always the same.
 * @param name - The assistant's first name.
 * @param gender - The persona's gender, as the API resolved it from the first name.
 * @returns The persona.
 */
export function personaFor(name: string, gender: AiAssistantPersonaGender): AiAssistantPersona {
  const slug: string = personaSlug(name)
  const own: AiAssistantPersona | undefined = ASSISTANT_CASTING.find(
    (persona: AiAssistantPersona): boolean => persona.slug === slug,
  )
  if (own) return own
  const sameGender: AiAssistantPersona[] = ASSISTANT_CASTING.filter(
    (persona: AiAssistantPersona): boolean => persona.gender === gender,
  )
  return sameGender[stableHash(slug) % sameGender.length] ?? ASSISTANT_DEFAULT_PERSONA
}

/**
 * The portrait of a casting persona on the demo host.
 * @param demoUrl - The assistant's demo link, which names the host.
 * @param slug - The persona's slug.
 * @returns The image address.
 */
export function personaPortraitUrl(demoUrl: string, slug: string): string {
  return `${portraitOrigin(demoUrl)}/avatars/${slug}.webp`
}

/**
 * The portrait an assistant shows, on its demo host.
 * @param demoUrl - The assistant's demo link.
 * @param name - The assistant's first name.
 * @param gender - The persona's gender.
 * @returns The image address.
 */
export function assistantPortraitUrl(demoUrl: string, name: string, gender: AiAssistantPersonaGender): string {
  return personaPortraitUrl(demoUrl, personaFor(name, gender).slug)
}

/**
 * The disc behind a portrait, as the widget draws it: the business's accent washed to a tint.
 * @param accentColor - The business's accent colour, or null when it has none.
 * @returns A CSS background value.
 */
export function portraitDiscBackground(accentColor: string | null): string {
  return accentColor ? `color-mix(in srgb, ${accentColor} 28%, white)` : 'var(--app-surface-2)'
}
