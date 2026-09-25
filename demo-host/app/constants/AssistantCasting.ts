import type { AiAssistantPersona } from '~/types/AiAssistant'

/** The persona of an assistant created without a first name, and the face of any feminine name not in the casting. */
export const ASSISTANT_DEFAULT_PERSONA: AiAssistantPersona = { name: 'Sofia', slug: 'sofia', gender: 'feminine' }

/**
 * The six receptionists, each with a portrait shipped as `public/avatars/{slug}.webp`. The API rotates through the
 * same first names when it creates an assistant (`PERSONA_FIRST_NAMES`), and the dashboard offers them as faces.
 */
export const ASSISTANT_CASTING: AiAssistantPersona[] = [
  ASSISTANT_DEFAULT_PERSONA,
  { name: 'Hugo', slug: 'hugo', gender: 'masculine' },
  { name: 'Léa', slug: 'lea', gender: 'feminine' },
  { name: 'Marc', slug: 'marc', gender: 'masculine' },
  { name: 'Inès', slug: 'ines', gender: 'feminine' },
  { name: 'Nathan', slug: 'nathan', gender: 'masculine' },
]
