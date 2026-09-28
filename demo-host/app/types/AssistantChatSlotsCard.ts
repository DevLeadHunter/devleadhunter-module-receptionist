import type {
  AssistantAppointmentDay,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantDayPeriod,
  AssistantSlotChoice,
  AssistantSlotsState,
  AssistantWidgetLanguage,
} from '~/types/AiAssistant'

export type AssistantChatSlotsCardProps = {
  language: AssistantWidgetLanguage
  bookingMode: AssistantBookingMode
  slotsState: AssistantSlotsState
  days: AssistantAppointmentDay[]
  times: AssistantAppointmentTime[]
  hasMoreTimes: boolean
  hasPreviousPage: boolean
  kinds: string[]
  chosenSlots: AssistantSlotChoice[]
  chosenTime: AssistantAppointmentTime | null
  chosenKind: string | null
  canContinue: boolean
}

export type AssistantChatSlotsCardEmits = {
  'toggle-slot': [date: string, period: AssistantDayPeriod]
  'choose-time': [time: AssistantAppointmentTime]
  'choose-kind': [kind: string]
  'first-page': []
  more: []
  confirm: []
  cancel: []
}
