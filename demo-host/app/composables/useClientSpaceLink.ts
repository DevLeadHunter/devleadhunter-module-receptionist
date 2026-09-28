import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type {
  AiAssistantClientRenew,
  AiAssistantClientRenewState,
  AiAssistantClientSpace,
  AiAssistantClientSpaceLoad,
  AiAssistantClientSpaceState,
} from '~/types/AiAssistantClientSpace'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { ClientSpaceLanguageUtils } from '~/utils/ClientSpaceLanguageUtils'

/** Where the browser keeps the latest link of a space, so an icon on the home screen outlives the link it saved. */
const STORED_LINK_PREFIX: string = 'client-space-link:'

/**
 * The assistant a token names (its first segment), to key the link the browser keeps.
 * @param value - The token.
 * @returns The assistant's id as written in the token, or an empty string for the example.
 */
function tokenAssistantId(value: string): string {
  return /^\d+\./.test(value) ? (value.split('.')[0] ?? '') : ''
}

/**
 * The client's personal link: the space it opens, a fresh link kept at each visit, a new one by email once it lapsed.
 * @returns The link's token and API address, the space it opened, and how to load it, keep it fresh and renew it.
 */
export function useClientSpaceLink(): UseClientSpaceLinkReturn {
  const route: ReturnType<typeof useRoute> = useRoute()
  const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()

  const state: Ref<AiAssistantClientSpaceState> = ref('loading')
  const space: Ref<AiAssistantClientSpace | null> = ref(null)
  const renewState: Ref<AiAssistantClientRenewState> = ref('idle')

  const token: ComputedRef<string> = computed((): string => String(route.params.token ?? ''))

  const endpoint: ComputedRef<string> = computed(
    (): string => `${config.public.apiBase}/api/v1/ai-assistants/client/${encodeURIComponent(token.value)}`,
  )

  /**
   * The latest link the browser kept for the same space as the URL's token.
   * @returns The stored token, or null when there is none (or no storage).
   */
  function storedFreshToken(): string | null {
    const id: string = tokenAssistantId(token.value)
    if (!id) return null
    try {
      return window.localStorage.getItem(`${STORED_LINK_PREFIX}${id}`)
    } catch {
      return null
    }
  }

  /**
   * Move the URL and the browser's memory to the fresh link, so the icon on the home screen keeps opening the space.
   * @param fresh - The fresh token.
   */
  function adoptFreshToken(fresh: string): void {
    const id: string = tokenAssistantId(fresh)
    try {
      if (id) window.localStorage.setItem(`${STORED_LINK_PREFIX}${id}`, fresh)
    } catch {
      // Private browsing or storage off: the URL still moves.
    }
    const path: string = `/client/${fresh}`
    if (window.location.pathname !== path) {
      window.history.replaceState(window.history.state, '', `${path}${window.location.search}${window.location.hash}`)
    }
  }

  /**
   * Load the space the link opens; a lapsed link falls back on the fresher one the browser kept, if any.
   * @returns The page's state, and the space when it opened.
   */
  async function fetchSpace(): Promise<AiAssistantClientSpaceLoad> {
    try {
      return { state: 'ready', space: await $fetch<AiAssistantClientSpace>(endpoint.value) }
    } catch (error: unknown) {
      const status: number | undefined = ApiRefusalUtils.status(error)
      if (status === 401) {
        const stored: string | null = storedFreshToken()
        if (stored && stored !== token.value) {
          // The link kept on the home screen lapsed, but the space was opened since: follow the fresher one.
          window.location.replace(`/client/${stored}${window.location.search}${window.location.hash}`)
          return { state: 'loading', space: null }
        }
        return { state: 'expired', space: null }
      }
      if (status === 404) return { state: 'invalid', space: null }
      return { state: 'unavailable', space: null }
    }
  }

  /**
   * Show what a load gave (the legacy language codes read as the offered ones), and move to the fresh link it carries.
   * @param load - The load's state, and the space when it opened.
   */
  function setLoadResult(load: AiAssistantClientSpaceLoad): void {
    state.value = load.state
    space.value = load.space ? ClientSpaceLanguageUtils.spaceWithOfferedLanguages(load.space) : null
    if (load.state === 'ready' && load.space?.fresh_token) adoptFreshToken(load.space.fresh_token)
  }

  /**
   * Switch to the « lien expiré » screen when the link lapsed during the visit.
   * @param error - What `$fetch` threw.
   * @returns True when the link had expired.
   */
  function showExpiredOnUnauthorized(error: unknown): boolean {
    if (ApiRefusalUtils.status(error) !== 401) return false
    state.value = 'expired'
    space.value = null
    return true
  }

  /**
   * The message a failed call shows, unless the link lapsed: the page then switches to the « lien expiré » screen.
   * @param error - What `$fetch` threw.
   * @param fallback - The message when the API gave no readable reason.
   * @returns Null on a 401, else the API's detail or the fallback.
   */
  function failureMessage(error: unknown, fallback: string): string | null {
    if (showExpiredOnUnauthorized(error)) return null
    return ApiRefusalUtils.detail(error) ?? fallback
  }

  /**
   * Ask for a fresh link: it goes to the business's email address, never shown here.
   * @returns A promise resolved once the API answered.
   */
  async function renewLink(): Promise<void> {
    renewState.value = 'sending'
    try {
      const answer: AiAssistantClientRenew = await $fetch<AiAssistantClientRenew>(`${endpoint.value}/renew`, {
        method: 'POST',
      })
      renewState.value = answer.sent ? 'sent' : 'failed'
    } catch {
      renewState.value = 'failed'
    }
  }

  return {
    token,
    endpoint,
    state,
    space,
    renewState,
    fetchSpace,
    setLoadResult,
    showExpiredOnUnauthorized,
    failureMessage,
    renewLink,
  }
}
