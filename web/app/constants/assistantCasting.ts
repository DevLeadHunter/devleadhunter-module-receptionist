import type { AiAssistantPersona } from '~/types/AiAssistant'

/** The persona of an assistant created without a first name, and the face of any feminine name not in the casting. */
export const ASSISTANT_DEFAULT_PERSONA: AiAssistantPersona = { name: 'Sofia', slug: 'sofia', gender: 'feminine' }

/**
 * The six receptionists a customer can pick a face from, in the order the API rotates through their first names.
 * Each portrait is served by the demo host as `/avatars/{slug}.webp`.
 */
export const ASSISTANT_CASTING: AiAssistantPersona[] = [
  ASSISTANT_DEFAULT_PERSONA,
  { name: 'Hugo', slug: 'hugo', gender: 'masculine' },
  { name: 'Léa', slug: 'lea', gender: 'feminine' },
  { name: 'Marc', slug: 'marc', gender: 'masculine' },
  { name: 'Inès', slug: 'ines', gender: 'feminine' },
  { name: 'Nathan', slug: 'nathan', gender: 'masculine' },
]
