import type { Ref } from 'vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import type {
  AiAssistantClientMailbox,
  AiAssistantClientMailboxConnect,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import type { UseClientSpaceMailboxReturn } from '~/types/UseClientSpaceMailbox'
import { ConsentTabUtils } from '~/utils/ConsentTabUtils'

/**
 * The client's Gmail: connected in a Google tab, disconnected after a confirmation.
 * @param link - The client's link: the space to update and the API to call.
 * @returns What is in flight, what failed, and the actions.
 */
export function useClientSpaceMailbox(link: UseClientSpaceLinkReturn): UseClientSpaceMailboxReturn {
  const isMailboxBusy: Ref<boolean> = ref(false)
  const mailboxError: Ref<string | null> = ref(null)
  let isAwaitingGoogleConsent: boolean = false

  /**
   * Open Google's consent page in a new tab to connect the client's Gmail.
   * @returns A promise resolved once the tab is on its way to Google, or once the failure is shown.
   */
  async function connectMailbox(): Promise<void> {
    if (!link.space.value || isMailboxBusy.value) return
    mailboxError.value = null
    isMailboxBusy.value = true
    try {
      await ConsentTabUtils.open(async (): Promise<string> => {
        const consent: AiAssistantClientMailboxConnect = await $fetch<AiAssistantClientMailboxConnect>(
          `${link.endpoint.value}/mailbox/connect`,
          { method: 'POST' },
        )
        return consent.url
      })
      isAwaitingGoogleConsent = true
    } catch (error: unknown) {
      mailboxError.value = link.failureMessage(error, 'Connexion indisponible, réessayez dans un instant.')
    } finally {
      isMailboxBusy.value = false
    }
  }

  /**
   * Disconnect the Gmail after a confirmation: no more reply drafts are prepared.
   * @returns A promise resolved once the API answered.
   */
  async function disconnectMailbox(): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isMailboxBusy.value) return
    const confirmed: boolean = window.confirm(
      'Déconnecter votre boîte mail ? Plus aucune réponse ne sera préparée dans vos brouillons.',
    )
    if (!confirmed) return
    isMailboxBusy.value = true
    mailboxError.value = null
    try {
      current.mailbox = await $fetch<AiAssistantClientMailbox>(`${link.endpoint.value}/mailbox`, { method: 'DELETE' })
    } catch (error: unknown) {
      mailboxError.value = link.failureMessage(error, 'Déconnexion impossible, réessayez dans un instant.')
    } finally {
      isMailboxBusy.value = false
    }
  }

  /** Open the mailbox screen clean: no error left by an earlier visit. */
  function clearMailboxFeedback(): void {
    mailboxError.value = null
  }

  /**
   * Reload the mailbox's state when the client comes back from the Google tab.
   * @returns A promise resolved once the mailbox is reloaded, or once the failure is handled.
   */
  async function reloadOnReturnFromGoogle(): Promise<void> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (document.visibilityState !== 'visible' || !isAwaitingGoogleConsent || !current) return
    try {
      const fresh: AiAssistantClientSpace = await $fetch<AiAssistantClientSpace>(link.endpoint.value)
      current.mailbox = fresh.mailbox
      if (fresh.mailbox?.status === 'connected') isAwaitingGoogleConsent = false
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

  return { isMailboxBusy, mailboxError, connectMailbox, disconnectMailbox, clearMailboxFeedback }
}
