import type { SelectFieldOption } from '~/types/SelectField'

/** The tones a receptionist can be given, as chips; a tone typed before the chips existed is offered beside them. */
export const ASSISTANT_TONE_OPTIONS: SelectFieldOption<string>[] = [
  { value: 'chaleureux', label: 'Chaleureux' },
  { value: 'professionnel', label: 'Professionnel' },
  { value: 'concis', label: 'Concis' },
  { value: 'rassurant', label: 'Rassurant' },
  { value: 'direct', label: 'Direct' },
  { value: 'décontracté', label: 'Décontracté' },
  { value: 'enjoué', label: 'Enjoué' },
]
