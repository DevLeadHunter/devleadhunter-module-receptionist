import type {
  AssistantAppointmentDay,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantDayPeriod,
  AssistantSlotChoice,
  AssistantSlotsState,
  AssistantWidgetLang,
} from '~/types/AiAssistant'

export type AssistantChatSlotsCardProps = {
  lang: AssistantWidgetLang
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
