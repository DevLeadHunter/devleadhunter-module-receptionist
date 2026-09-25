import { createAvatar } from '@dicebear/core'
import type { Options as NotionistsOptions } from '@dicebear/notionists'
import * as notionists from '@dicebear/notionists'
import type { AiAssistantPersona, AiAssistantPersonaGender } from '~/types/AiAssistant'
import { ASSISTANT_CASTING, ASSISTANT_DEFAULT_PERSONA } from '~/constants/AssistantCasting'

/** One hair style of the illustration set. */
type HairStyle = NonNullable<NotionistsOptions['hair']>[number]

/** Hair styles of the illustration set that read as feminine (long hair, bobs, buns, ponytails, headbands). */
const FEMININE_HAIR: HairStyle[] = [
  'variant02',
  'variant04',
  'variant08',
  'variant10',
  'variant23',
  'variant28',
  'variant36',
  'variant37',
  'variant39',
  'variant41',
  'variant43',
  'variant45',
  'variant46',
  'variant47',
  'variant48',
  'variant57',
  'variant58',
  'variant63',
]

/** Hair styles of the illustration set that read as masculine (short cuts, no hats, no punk crests). */
const MASCULINE_HAIR: HairStyle[] = [
  'variant01',
  'variant03',
  'variant05',
  'variant06',
  'variant07',
  'variant09',
  'variant13',
  'variant15',
  'variant16',
  'variant17',
  'variant18',
  'variant19',
  'variant21',
  'variant24',
  'variant25',
  'variant27',
  'variant30',
  'variant31',
  'variant34',
  'variant35',
  'variant38',
  'variant49',
  'variant52',
  'variant53',
  'variant54',
  'variant55',
  'variant56',
  'variant60',
]

/** Chance, in percent, that a masculine persona wears a beard. */
const BEARD_PROBABILITY: number = 40

/** Chance, in percent, that a persona wears glasses. */
const GLASSES_PROBABILITY: number = 20

/**
 * The assistant's portrait: the photo of its casting persona, with a bust drawn from the name when the photo is
 * not shipped.
 */
export class AssistantAvatarUtils {
  /**
   * The photo to show, the same everywhere the assistant appears: the persona's own when the first name belongs
   * to the casting, else the face of a casting persona of the same gender, always the same for a given name.
   * @param name - The persona's first name.
   * @param gender - The persona's gender, as the API resolved it from the first name.
   * @returns The address of the shipped photo.
   */
  static portraitUrl(name: string, gender: AiAssistantPersonaGender | null): string {
    return `/avatars/${AssistantAvatarUtils.persona(name, gender).slug}.webp`
  }

  /**
   * A bust drawn from the persona's first name, as an SVG data URI ready for an `<img>`.
   * @param name - The persona's first name: the seed of the drawing.
   * @param gender - The persona's gender, which picks the hair styles and allows a beard.
   * @param backgroundColor - The disc behind the bust, as a hex colour.
   * @returns The data URI.
   */
  static dataUri(name: string, gender: AiAssistantPersonaGender | null, backgroundColor: string): string {
    const isMasculine: boolean = gender === 'masculine'
    return createAvatar(notionists, {
      seed: name.trim().toLowerCase() || 'assistant',
      radius: 50,
      backgroundColor: [backgroundColor.replace(/^#/, '')],
      hair: isMasculine ? MASCULINE_HAIR : FEMININE_HAIR,
      beardProbability: isMasculine ? BEARD_PROBABILITY : 0,
      glassesProbability: GLASSES_PROBABILITY,
      gestureProbability: 0,
      bodyIconProbability: 0,
    }).toDataUri()
  }

  /**
   * The casting persona whose face a first name takes.
   * @param name - The persona's first name.
   * @param gender - The persona's gender; feminine when unknown.
   * @returns The persona of that name, else one of the same gender picked from the name.
   */
  private static persona(name: string, gender: AiAssistantPersonaGender | null): AiAssistantPersona {
    const slug: string = AssistantAvatarUtils.slug(name)
    const own: AiAssistantPersona | undefined = ASSISTANT_CASTING.find(
      (persona: AiAssistantPersona): boolean => persona.slug === slug,
    )
    if (own) return own
    const sameGender: AiAssistantPersona[] = ASSISTANT_CASTING.filter(
      (persona: AiAssistantPersona): boolean => persona.gender === (gender ?? 'feminine'),
    )
    return sameGender[AssistantAvatarUtils.hash(slug) % sameGender.length] ?? ASSISTANT_DEFAULT_PERSONA
  }

  /**
   * A first name as a file name (« Léa » → `lea`, « Jean-Pierre » → `jean-pierre`).
   * @param name - The first name.
   * @returns The slug.
   */
  private static slug(name: string): string {
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
  private static hash(value: string): number {
    let hash: number = 0
    for (const character of value) hash = (hash * 31 + character.charCodeAt(0)) >>> 0
    return hash
  }
}
