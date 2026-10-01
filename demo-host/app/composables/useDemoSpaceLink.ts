import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type {
  AiAssistantClientRenewState,
  AiAssistantClientSpace,
  AiAssistantClientSpaceLoad,
  AiAssistantClientSpaceState,
} from '~/types/AiAssistantClientSpace'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantConversationStorageUtils } from '~/utils/AssistantConversationStorageUtils'
import { ClientSpaceLanguageUtils } from '~/utils/ClientSpaceLanguageUtils'

/**
 * The prospect's demo space, loaded with the widget sessions this browser kept, in the shape of the client's link.
 * @returns The demo's API address, the space it opened, and how to load it.
 */
export function useDemoSpaceLink(): UseClientSpaceLinkReturn {
  const route: ReturnType<typeof useRoute> = useRoute()
  const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()

  const state: Ref<AiAssistantClientSpaceState> = ref('loading')
  const space: Ref<AiAssistantClientSpace | null> = ref(null)
  const renewState: Ref<AiAssistantClientRenewState> = ref('idle')

  const slug: ComputedRef<string> = computed((): string => String(route.params.slug ?? ''))

  /** A demo space has no personal link: every write of the client space refuses it. */
  const token: ComputedRef<string> = computed((): string => '')

  const endpoint: ComputedRef<string> = computed(
    (): string => `${config.public.apiBase}/api/v1/ai-assistants/public/${encodeURIComponent(slug.value)}/space`,
  )

  /**
   * Load the demo space with the visitor's own widget sessions, so it lists their requests and no one else's.
   * @returns The page's state, and the space when it opened.
   */
  async function fetchSpace(): Promise<AiAssistantClientSpaceLoad> {
    try {
      const loaded: AiAssistantClientSpace = await $fetch<AiAssistantClientSpace>(endpoint.value, {
        method: 'POST',
        body: { session_ids: AssistantConversationStorageUtils.sessionIds(slug.value) },
      })
      return { state: 'ready', space: loaded }
    } catch (error: unknown) {
      return { state: ApiRefusalUtils.status(error) === 404 ? 'invalid' : 'unavailable', space: null }
    }
  }

  /**
   * Show what a load gave, the legacy language codes read as the offered ones.
   * @param load - The load's state, and the space when it opened.
   */
  function setLoadResult(load: AiAssistantClientSpaceLoad): void {
    state.value = load.state
    space.value = load.space ? ClientSpaceLanguageUtils.spaceWithOfferedLanguages(load.space) : null
  }

  /**
   * A demo space never expires by link: no call switches it to the « lien expiré » screen.
   * @returns Always false.
   */
  function showExpiredOnUnauthorized(): boolean {
    return false
  }

  /**
   * The message a refused call shows.
   * @param error - What `$fetch` threw.
   * @param fallback - The message when the API gave no readable reason.
   * @returns The API's detail, or the fallback.
   */
  function failureMessage(error: unknown, fallback: string): string {
    return ApiRefusalUtils.detail(error) ?? fallback
  }

  /**
   * A demo space has no link to renew.
   * @returns A promise already resolved.
   */
  function renewLink(): Promise<void> {
    return Promise.resolve()
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
