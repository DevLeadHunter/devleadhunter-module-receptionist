import { createAvatar } from '@dicebear/core'
import type { Options as NotionistsOptions } from '@dicebear/notionists'
import * as notionists from '@dicebear/notionists'
import type { AiAssistantPersonaGender } from '~/types/AiAssistant'
import { ASSISTANT_DEFAULT_PORTRAITS, ASSISTANT_PORTRAIT_SLUGS } from '~/constants/assistantPortraits'

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
 * The assistant's portrait: a photo shipped for the persona when there is one, else a bust drawn from the name.
 */
export class AssistantAvatarUtils {
  /**
   * The portrait to show, the same everywhere the assistant appears.
   * @param name - The persona's first name.
   * @param gender - The persona's gender.
   * @param backgroundColor - The disc behind a drawn bust, as a hex colour.
   * @returns The address of a shipped photo, or a data URI of the drawn bust.
   */
  static portraitUrl(name: string, gender: AiAssistantPersonaGender | null, backgroundColor: string): string {
    const slug: string = AssistantAvatarUtils.slug(name)
    if (ASSISTANT_PORTRAIT_SLUGS.includes(slug)) return `/avatars/${slug}.webp`
    const resolvedGender: AiAssistantPersonaGender = gender ?? 'feminine'
    if (ASSISTANT_DEFAULT_PORTRAITS[resolvedGender]) return `/avatars/default-${resolvedGender}.webp`
    return AssistantAvatarUtils.dataUri(name, gender, backgroundColor)
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
}
