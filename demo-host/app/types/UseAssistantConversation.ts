import type { ComputedRef, Ref } from 'vue'
import type {
  AssistantAppointmentDay,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantChatMessage,
  AssistantDayPeriod,
  AssistantSlotChoice,
  AssistantSlotsState,
  AssistantWidgetLang,
} from '~/types/AiAssistant'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantContactDetails } from '~/types/AssistantChatContactForm'
import type { AssistantDemoScriptStep } from '~/types/AssistantDemoScript'

export type UseAssistantConversationReturn = {
  messages: Ref<AssistantChatMessage[]>
  lang: Ref<AssistantWidgetLang>
  offeredLanguages: ComputedRef<AssistantWidgetLang[]>
  suggestions: ComputedRef<string[]>
  draft: Ref<string>
  isBusy: Ref<boolean>
  photoPreviews: Ref<Record<number, string>>
  photosRemaining: Ref<number>
  isPhotoPanelOpen: Ref<boolean>
  isSlotPanelOpen: Ref<boolean>
  showLeadForm: Ref<boolean>
  leadSent: Ref<boolean>
  isSubmittingLead: Ref<boolean>
  leadNeedPrefill: Ref<string>
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
  canContinueBooking: ComputedRef<boolean>
  pickedSummary: ComputedRef<string>
  showChips: ComputedRef<boolean>
  showCallbackBar: ComputedRef<boolean>
  lastLeadSummary: Ref<AssistantLeadSummary | null>
  hasPlayedExample: Ref<boolean>
  restore: () => void
  greet: () => Promise<void>
  playExample: (steps: AssistantDemoScriptStep[]) => Promise<void>
  setLang: (code: AssistantWidgetLang) => void
  sendText: (text: string) => Promise<void>
  sendDraft: () => Promise<void>
  openPhotoPanel: () => void
  closePhotoPanel: () => void
  sendPhoto: (file: File) => Promise<void>
  openSlotPanel: () => Promise<void>
  closeSlotPanel: () => void
  loadFirstSlotsPage: () => Promise<void>
  showMoreTimes: () => Promise<void>
  toggleSlot: (date: string, period: AssistantDayPeriod) => void
  chooseTime: (time: AssistantAppointmentTime) => void
  chooseKind: (kind: string) => void
  confirmSlots: () => void
  openLeadForm: () => void
  cancelLeadForm: () => void
  submitLead: (details: AssistantContactDetails) => Promise<void>
  releasePhotoPreviews: () => void
}
