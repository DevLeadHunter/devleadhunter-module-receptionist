import type { ClientSpaceRequestTypeOption } from '~/types/ClientSpaceSettings'

/** The request types a client can have texted at once, the ones that cannot wait first (same order as the dashboard). */
export const CLIENT_SPACE_REQUEST_TYPE_OPTIONS: ClientSpaceRequestTypeOption[] = [
  { value: 'quote', label: 'Devis' },
  { value: 'appointment', label: 'Rendez-vous' },
  { value: 'urgent', label: 'Urgence' },
  { value: 'question', label: 'Question' },
  { value: 'other', label: 'Autre' },
]
