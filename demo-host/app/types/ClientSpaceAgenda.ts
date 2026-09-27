import type {
  AiAssistantClientAppointment,
  AiAssistantClientCalendar,
  AiAssistantClientCalendarUpdate,
  AiAssistantClientRequest,
} from '~/types/AiAssistantClientSpace'

/** Props of the client-space agenda section. */
export type ClientSpaceAgendaProps = {
  calendar: AiAssistantClientCalendar
  appointments: AiAssistantClientAppointment[]
  /** The latest requests; the appointment requests still waiting are listed as to confirm. */
  requests: AiAssistantClientRequest[]
  assistantName: string
  isBusy: boolean
  errorMessage: string | null
  hasSaved: boolean
  readOnly: boolean
}

/** Events of the ClientSpaceAgenda component. */
export type ClientSpaceAgendaEmits = {
  connect: []
  save: [update: AiAssistantClientCalendarUpdate]
  disconnect: []
  'open-request': [requestId: number]
}
