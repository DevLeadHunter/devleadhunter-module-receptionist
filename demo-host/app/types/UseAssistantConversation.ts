import type { ComputedRef, Ref } from 'vue'
import type { AssistantThreadMessage, AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantDemoScriptStep } from '~/types/AssistantDemoScript'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import type { UseAssistantLeadFormReturn } from '~/types/UseAssistantLeadForm'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'

export type UseAssistantConversationReturn = {
  messages: Ref<AssistantThreadMessage[]>
  language: Ref<AssistantWidgetLanguage>
  offeredLanguages: ComputedRef<AssistantWidgetLanguage[]>
  suggestions: ComputedRef<string[]>
  draft: Ref<string>
  isBusy: Ref<boolean>
  isStreaming: Ref<boolean>
  hasSentLead: Ref<boolean>
  isAssistantUnavailable: Ref<boolean>
  canPlayExample: ComputedRef<boolean>
  shouldShowOpeningChips: ComputedRef<boolean>
  followUps: ComputedRef<string[]>
  shouldShowActionChips: ComputedRef<boolean>
  shouldShowCallbackBar: ComputedRef<boolean>
  hasPlayedExample: Ref<boolean>
  restore: () => void
  restoreFromHost: (raw: string | null) => void
  greet: () => Promise<void>
  playExample: (steps: AssistantDemoScriptStep[]) => Promise<void>
  setLanguage: (language: AssistantWidgetLanguage) => void
  sendSuggestion: (text: string) => Promise<boolean>
  sendDraft: () => Promise<void>
} & Pick<
  UseAssistantBookingReturn,
  | 'bookingMode'
  | 'slotsState'
  | 'slotDays'
  | 'slotTimes'
  | 'hasMoreTimes'
  | 'hasPreviousSlotsPage'
  | 'appointmentKinds'
  | 'chosenSlots'
  | 'chosenTime'
  | 'chosenKind'
  | 'canContinueBooking'
  | 'pickedSummary'
  | 'isSlotPanelOpen'
  | 'openSlotPanel'
  | 'closeSlotPanel'
  | 'loadFirstSlotsPage'
  | 'showMoreTimes'
  | 'toggleSlot'
  | 'chooseTime'
  | 'chooseKind'
  | 'confirmSlots'
> &
  Pick<
    UseAssistantPhotoUploadReturn,
    | 'photoPreviews'
    | 'photosRemaining'
    | 'leadNeedPrefill'
    | 'isPhotoPanelOpen'
    | 'openPhotoPanel'
    | 'closePhotoPanel'
    | 'sendPhoto'
    | 'releasePhotoPreviews'
  > &
  Pick<
    UseAssistantLeadFormReturn,
    | 'isLeadFormOpen'
    | 'isSubmittingLead'
    | 'leadPrefill'
    | 'lastLeadSummary'
    | 'openLeadForm'
    | 'cancelLeadForm'
    | 'submitLead'
  >
