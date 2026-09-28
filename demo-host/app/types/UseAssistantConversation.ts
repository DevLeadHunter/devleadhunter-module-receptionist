import type { ComputedRef, Ref } from 'vue'
import type { AssistantChatMessage, AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantDemoScriptStep } from '~/types/AssistantDemoScript'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import type { UseAssistantLeadFormReturn } from '~/types/UseAssistantLeadForm'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'

export type UseAssistantThreadReturn = {
  messages: Ref<AssistantChatMessage[]>
  language: Ref<AssistantWidgetLanguage>
  offeredLanguages: ComputedRef<AssistantWidgetLanguage[]>
  suggestions: ComputedRef<string[]>
  draft: Ref<string>
  isBusy: Ref<boolean>
  isStreaming: Ref<boolean>
  hasSentLead: Ref<boolean>
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
  sendText: (text: string) => Promise<void>
  sendDraft: () => Promise<void>
}

export type UseAssistantConversationReturn = UseAssistantThreadReturn &
  UseAssistantBookingReturn &
  UseAssistantPhotoUploadReturn &
  UseAssistantLeadFormReturn
