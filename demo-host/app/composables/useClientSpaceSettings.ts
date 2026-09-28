import type { Ref } from 'vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type {
  AiAssistantClientGoogleProfile,
  AiAssistantClientLimit,
  AiAssistantClientLimitUpdate,
  AiAssistantClientPortal,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
  AiAssistantClientSpace,
  AiAssistantClientTestSms,
  AiAssistantClientTestSmsState,
} from '~/types/AiAssistantClientSpace'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import type { UseClientSpaceSettingsReturn } from '~/types/UseClientSpaceSettings'

/**
 * The settings section's saves: receptionist, alerts, test SMS, imposed answers, Google profile, billing portal.
 * @param link - The client's link: the space to update and the API to call.
 * @returns What is in flight, what went through or failed, and the actions.
 */
export function useClientSpaceSettings(link: UseClientSpaceLinkReturn): UseClientSpaceSettingsReturn {
  const isSavingSettings: Ref<boolean> = ref(false)
  const settingsError: Ref<string | null> = ref(null)
  const hasSavedSettings: Ref<boolean> = ref(false)
  const testSmsState: Ref<AiAssistantClientTestSmsState> = ref('idle')
  const testSmsMessage: Ref<string | null> = ref(null)
  const isSavingLimits: Ref<boolean> = ref(false)
  const limitsError: Ref<string | null> = ref(null)
  const hasSavedLimits: Ref<boolean> = ref(false)
  const isSavingGoogleProfile: Ref<boolean> = ref(false)
  const googleProfileError: Ref<string | null> = ref(null)
  const isOpeningBillingPortal: Ref<boolean> = ref(false)
  const billingPortalError: Ref<string | null> = ref(null)

  /**
   * Save the settings the client changed.
   * @param update - The changed fields only.
   * @returns A promise resolved once the API answered.
   */
  async function saveSettings(update: AiAssistantClientSettingsUpdate): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isSavingSettings.value) return
    isSavingSettings.value = true
    settingsError.value = null
    hasSavedSettings.value = false
    try {
      current.settings = await $fetch<AiAssistantClientSettings>(`${link.endpoint.value}/settings`, {
        method: 'PATCH',
        body: update,
      })
      if (update.assistant_name) current.assistant_name = current.settings.assistant_name
      hasSavedSettings.value = true
    } catch (error: unknown) {
      settingsError.value = link.failureMessage(error, 'Enregistrement impossible, réessayez dans un instant.')
    } finally {
      isSavingSettings.value = false
    }
  }

  /**
   * Text the saved alert mobile once, so the client sees the alerts arrive.
   * @returns A promise resolved once the API answered.
   */
  async function sendTestSms(): Promise<void> {
    if (testSmsState.value === 'sending') return
    testSmsState.value = 'sending'
    testSmsMessage.value = null
    try {
      const answer: AiAssistantClientTestSms = await $fetch<AiAssistantClientTestSms>(
        `${link.endpoint.value}/alerts/test-sms`,
        { method: 'POST' },
      )
      testSmsState.value = answer.sent ? 'sent' : 'failed'
      testSmsMessage.value = answer.sent ? `SMS envoyé au ${answer.to_label ?? 'mobile enregistré'}.` : answer.reason
    } catch (error: unknown) {
      testSmsState.value = 'failed'
      testSmsMessage.value = link.failureMessage(error, 'Envoi impossible pour le moment.')
    }
  }

  /**
   * Keep the business's edits of what the receptionist says on prices, delays, warranties.
   * @param updates - Every subject, as edited.
   * @returns A promise resolved once the API answered.
   */
  async function saveLimits(updates: AiAssistantClientLimitUpdate[]): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isSavingLimits.value) return
    isSavingLimits.value = true
    limitsError.value = null
    hasSavedLimits.value = false
    try {
      current.limits = await $fetch<AiAssistantClientLimit[]>(`${link.endpoint.value}/limits`, {
        method: 'PATCH',
        body: { limits: updates },
      })
      hasSavedLimits.value = true
    } catch (error: unknown) {
      limitsError.value = link.failureMessage(error, 'Enregistrement impossible, réessayez dans un instant.')
    } finally {
      isSavingLimits.value = false
    }
  }

  /**
   * Tell the API whether the receptionist's address is on the business's Google profile.
   * @param isLinked - True when the client ticked the box.
   * @returns A promise resolved once the API answered.
   */
  async function setGoogleProfileLinked(isLinked: boolean): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current?.google_profile || isSavingGoogleProfile.value) return
    isSavingGoogleProfile.value = true
    googleProfileError.value = null
    try {
      current.google_profile = await $fetch<AiAssistantClientGoogleProfile>(`${link.endpoint.value}/google-profile`, {
        method: 'POST',
        body: { linked: isLinked },
      })
    } catch (error: unknown) {
      googleProfileError.value = link.failureMessage(error, 'Enregistrement impossible, réessayez dans un instant.')
    } finally {
      isSavingGoogleProfile.value = false
    }
  }

  /**
   * Open the Stripe billing portal of the client's subscription.
   * @returns A promise resolved once redirected, or once the failure is shown.
   */
  async function openBillingPortal(): Promise<void> {
    if (isOpeningBillingPortal.value) return
    isOpeningBillingPortal.value = true
    billingPortalError.value = null
    try {
      const portal: AiAssistantClientPortal = await $fetch<AiAssistantClientPortal>(
        `${link.endpoint.value}/billing-portal`,
        { method: 'POST' },
      )
      window.location.assign(portal.url)
    } catch (error: unknown) {
      billingPortalError.value = link.failureMessage(error, 'Ouverture impossible, réessayez dans un instant.')
      isOpeningBillingPortal.value = false
    }
  }

  /** Start a settings screen clean: no « Enregistré. », error nor test SMS outcome left by the previous one. */
  function clearScreenFeedback(): void {
    hasSavedSettings.value = false
    settingsError.value = null
    testSmsState.value = 'idle'
    testSmsMessage.value = null
    hasSavedLimits.value = false
    limitsError.value = null
  }

  /**
   * Unlock the portal button when the browser restores this page from its back-forward cache.
   * @param event - The page-show event.
   */
  function onPageShow(event: PageTransitionEvent): void {
    if (event.persisted) isOpeningBillingPortal.value = false
  }

  onMounted((): void => {
    window.addEventListener('pageshow', onPageShow)
  })

  onBeforeUnmount((): void => {
    window.removeEventListener('pageshow', onPageShow)
  })

  return {
    isSavingSettings,
    settingsError,
    hasSavedSettings,
    testSmsState,
    testSmsMessage,
    isSavingLimits,
    limitsError,
    hasSavedLimits,
    isSavingGoogleProfile,
    googleProfileError,
    isOpeningBillingPortal,
    billingPortalError,
    saveSettings,
    sendTestSms,
    saveLimits,
    setGoogleProfileLinked,
    openBillingPortal,
    clearScreenFeedback,
  }
}
