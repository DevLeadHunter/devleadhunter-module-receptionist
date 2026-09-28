import type { Ref } from 'vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type {
  AiAssistantClientCalendar,
  AiAssistantClientCalendarConnect,
  AiAssistantClientCalendarUpdate,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'
import type { UseClientSpaceCalendarReturn } from '~/types/UseClientSpaceCalendar'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'

/**
 * The client's Google agenda: connected in a Google tab, its booking settings saved, disconnected.
 * @param link - The client's link: the space to update and the API to call.
 * @returns What is in flight, what went through or failed, and the actions.
 */
export function useClientSpaceCalendar(link: UseClientSpaceLinkReturn): UseClientSpaceCalendarReturn {
  const isCalendarBusy: Ref<boolean> = ref(false)
  const calendarError: Ref<string | null> = ref(null)
  const hasSavedCalendar: Ref<boolean> = ref(false)
  let isAwaitingGoogleConsent: boolean = false

  /**
   * Open Google's consent page in a new tab to connect the client's agenda.
   * @returns A promise resolved once the tab is on its way to Google, or once the failure is shown.
   */
  async function connectCalendar(): Promise<void> {
    if (!link.space.value || isCalendarBusy.value) return
    calendarError.value = null
    // Opened before the call: a tab opened after an await is blocked as a pop-up. It never sees this page.
    const tab: Window | null = window.open('about:blank', '_blank')
    if (tab) tab.opener = null
    isCalendarBusy.value = true
    try {
      const consent: AiAssistantClientCalendarConnect = await $fetch<AiAssistantClientCalendarConnect>(
        `${link.endpoint.value}/calendar/connect`,
        { method: 'POST' },
      )
      isAwaitingGoogleConsent = true
      if (tab) tab.location.href = consent.url
      else window.location.assign(consent.url)
    } catch (error: unknown) {
      tab?.close()
      calendarError.value = link.failureMessage(error, 'Connexion indisponible, réessayez dans un instant.')
    } finally {
      isCalendarBusy.value = false
    }
  }

  /**
   * Save the booking settings the client changed.
   * @param update - The changed settings only.
   * @returns A promise resolved once the API answered.
   */
  async function saveCalendar(update: AiAssistantClientCalendarUpdate): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isCalendarBusy.value) return
    isCalendarBusy.value = true
    calendarError.value = null
    hasSavedCalendar.value = false
    try {
      current.calendar = await $fetch<AiAssistantClientCalendar>(`${link.endpoint.value}/calendar`, {
        method: 'PATCH',
        body: update,
      })
      hasSavedCalendar.value = true
    } catch (error: unknown) {
      calendarError.value = link.failureMessage(error, 'Enregistrement impossible, réessayez dans un instant.')
    } finally {
      isCalendarBusy.value = false
    }
  }

  /**
   * Disconnect the agenda after a confirmation: appointments go back to requests the client confirms.
   * @returns A promise resolved once the API answered.
   */
  async function disconnectCalendar(): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isCalendarBusy.value) return
    const confirmed: boolean = window.confirm(
      'Déconnecter votre agenda ? Les visiteurs choisiront des demi-journées et vous confirmerez vous-même.',
    )
    if (!confirmed) return
    isCalendarBusy.value = true
    calendarError.value = null
    // « Enregistré. » belonged to the agenda that goes away.
    hasSavedCalendar.value = false
    try {
      current.calendar = await $fetch<AiAssistantClientCalendar>(`${link.endpoint.value}/calendar`, {
        method: 'DELETE',
      })
    } catch (error: unknown) {
      calendarError.value = link.failureMessage(error, 'Déconnexion impossible, réessayez dans un instant.')
    } finally {
      isCalendarBusy.value = false
    }
  }

  /** Open the agenda clean: no « Enregistré. » nor error left by an earlier visit. */
  function clearCalendarFeedback(): void {
    hasSavedCalendar.value = false
    calendarError.value = null
  }

  /**
   * Reload the agenda's state when the client comes back from the Google tab; unsaved settings stay as typed.
   * @returns A promise resolved once the agenda is reloaded, or once the failure is handled.
   */
  async function reloadOnReturnFromGoogle(): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (document.visibilityState !== 'visible' || !isAwaitingGoogleConsent || !current) return
    try {
      const fresh: AiAssistantClientSpace = await $fetch<AiAssistantClientSpace>(link.endpoint.value)
      current.calendar = fresh.calendar
      current.appointments = fresh.appointments
      if (fresh.calendar.status === 'connected') isAwaitingGoogleConsent = false
    } catch (error: unknown) {
      link.showExpiredOnUnauthorized(error)
    }
  }

  onMounted((): void => {
    document.addEventListener('visibilitychange', reloadOnReturnFromGoogle)
  })

  onBeforeUnmount((): void => {
    document.removeEventListener('visibilitychange', reloadOnReturnFromGoogle)
  })

  return {
    isCalendarBusy,
    calendarError,
    hasSavedCalendar,
    connectCalendar,
    saveCalendar,
    disconnectCalendar,
    clearCalendarFeedback,
  }
}
