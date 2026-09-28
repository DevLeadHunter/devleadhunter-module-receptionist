import type { Ref } from 'vue'
import type {
  AiAssistantClientLimitUpdate,
  AiAssistantClientSettingsUpdate,
  AiAssistantClientTestSmsState,
} from '~/types/AiAssistantClientSpace'

export type UseClientSpaceSettingsReturn = {
  isSavingSettings: Ref<boolean>
  settingsError: Ref<string | null>
  hasSavedSettings: Ref<boolean>
  testSmsState: Ref<AiAssistantClientTestSmsState>
  testSmsMessage: Ref<string | null>
  isSavingLimits: Ref<boolean>
  limitsError: Ref<string | null>
  hasSavedLimits: Ref<boolean>
  isSavingGoogleProfile: Ref<boolean>
  googleProfileError: Ref<string | null>
  isOpeningBillingPortal: Ref<boolean>
  billingPortalError: Ref<string | null>
  saveSettings: (update: AiAssistantClientSettingsUpdate) => Promise<void>
  sendTestSms: () => Promise<void>
  saveLimits: (updates: AiAssistantClientLimitUpdate[]) => Promise<void>
  setGoogleProfileLinked: (isLinked: boolean) => Promise<void>
  openBillingPortal: () => Promise<void>
  clearScreenFeedback: () => void
}
