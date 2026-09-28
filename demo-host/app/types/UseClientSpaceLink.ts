import type { ComputedRef, Ref } from 'vue'
import type {
  AiAssistantClientRenewState,
  AiAssistantClientSpace,
  AiAssistantClientSpaceLoad,
  AiAssistantClientSpaceState,
} from '~/types/AiAssistantClientSpace'

export type UseClientSpaceLinkReturn = {
  token: ComputedRef<string>
  endpoint: ComputedRef<string>
  state: Ref<AiAssistantClientSpaceState>
  space: Ref<AiAssistantClientSpace | null>
  renewState: Ref<AiAssistantClientRenewState>
  fetchSpace: () => Promise<AiAssistantClientSpaceLoad>
  setLoadResult: (load: AiAssistantClientSpaceLoad) => void
  showExpiredOnUnauthorized: (error: unknown) => boolean
  failureMessage: (error: unknown, fallback: string) => string | null
  renewLink: () => Promise<void>
}
