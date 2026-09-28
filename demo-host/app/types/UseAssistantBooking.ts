import type { ComputedRef, Ref } from 'vue'
import type {
  AssistantAppointmentDay,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantDayPeriod,
  AssistantSlotChoice,
  AssistantSlotRefusalCode,
  AssistantSlotsState,
} from '~/types/AiAssistant'

export type UseAssistantBookingReturn = {
  bookingMode: Ref<AssistantBookingMode>
  slotsState: Ref<AssistantSlotsState>
  slotDays: Ref<AssistantAppointmentDay[]>
  slotTimes: Ref<AssistantAppointmentTime[]>
  hasMoreTimes: Ref<boolean>
  hasPreviousSlotsPage: ComputedRef<boolean>
  appointmentKinds: Ref<string[]>
  chosenSlots: Ref<AssistantSlotChoice[]>
  chosenTime: Ref<AssistantAppointmentTime | null>
  chosenKind: Ref<string | null>
  chosenSlotsLine: ComputedRef<string>
  canContinueBooking: ComputedRef<boolean>
  pickedSummary: ComputedRef<string>
  hasOfferedBooking: Ref<boolean>
  isSlotPanelOpen: ComputedRef<boolean>
  openSlotPanel: () => Promise<void>
  closeSlotPanel: () => void
  loadFirstSlotsPage: () => Promise<void>
  showMoreTimes: () => Promise<void>
  toggleSlot: (date: string, period: AssistantDayPeriod) => void
  chooseTime: (time: AssistantAppointmentTime) => void
  chooseKind: (kind: string) => void
  confirmSlots: () => void
  forgetPicks: () => void
  offerSlotsAgain: (code: AssistantSlotRefusalCode) => Promise<void>
}
