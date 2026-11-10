import type { ComputedRef, Ref } from 'vue'
import type { UseToastReturn } from '~/types/Composables'
import type { ProspectDrawerExtensionProps } from '~/types/ProspectDrawerExtension'
import type { AiAssistantSummary } from '../types/AiAssistant'
import { computed, ref, watch } from 'vue'
import { useToast } from '~/composables/useToast'
import { AiAssistantService } from '../services/aiAssistantService'

/** What `useProspectAssistant` gives: the prospect's receptionist once looked up, and how to generate one. */
export type UseProspectAssistantReturn = {
  prospectAssistant: ComputedRef<AiAssistantSummary | null>
  assistantDemoUrl: ComputedRef<string>
  isGeneratingAssistant: Ref<boolean>
  generateAssistant: () => Promise<void>
}

/** The receptionist found for a prospect at one opening of the prospect drawer. */
type ProspectAssistantLookup = {
  openingId: number
  assistant: AiAssistantSummary | null
}

/**
 * The receptionist of the prospect the drawer shows, looked up at each opening and shared by the block and the button.
 * @param props - The props the prospect drawer hands to its module blocks.
 * @returns The prospect's receptionist, its demo link and the generation action.
 */
export function useProspectAssistant(props: ProspectDrawerExtensionProps): UseProspectAssistantReturn {
  const toast: UseToastReturn = useToast()
  const lookups: Ref<Record<number, ProspectAssistantLookup>> = useState(
    'assistant-prospect-lookups',
    (): Record<number, ProspectAssistantLookup> => ({}),
  )
  const isGeneratingAssistant: Ref<boolean> = ref(false)

  const prospectAssistant: ComputedRef<AiAssistantSummary | null> = computed(
    (): AiAssistantSummary | null => lookups.value[props.prospect.id]?.assistant ?? null,
  )

  /** The receptionist's demo URL, marked internal so previewing it never pollutes its analytics. */
  const assistantDemoUrl: ComputedRef<string> = computed((): string => {
    const url: string = prospectAssistant.value?.demo_url ?? ''

    if (!url) {
      return ''
    }
    return url.includes('?') ? `${url}&internal=1` : `${url}?internal=1`
  })

  /**
   * Find the receptionist already generated for the prospect, if any.
   * @param prospectId - The prospect shown.
   * @param openingId - The drawer opening the lookup belongs to.
   * @returns A promise resolved once the lookup completes.
   */
  async function lookUpAssistant(prospectId: number, openingId: number): Promise<void> {
    lookups.value = { ...lookups.value, [prospectId]: { openingId, assistant: null } }
    try {
      const assistant: AiAssistantSummary | null = await AiAssistantService.getForProspect(prospectId)

      if (lookups.value[prospectId]?.openingId !== openingId) {
        return
      }
      lookups.value = { ...lookups.value, [prospectId]: { openingId, assistant } }
    } catch {
      // Non-critical — the drawer falls back to the generation call to action.
    }
  }

  /**
   * Generate a receptionist for the prospect and surface its demo link.
   * @returns A promise resolved once the receptionist is generated.
   */
  async function generateAssistant(): Promise<void> {
    if (isGeneratingAssistant.value) {
      return
    }
    const prospectId: number = props.prospect.id
    isGeneratingAssistant.value = true
    try {
      const assistant: AiAssistantSummary = await AiAssistantService.create(prospectId)
      lookups.value = { ...lookups.value, [prospectId]: { openingId: props.openingId, assistant } }
      toast.success('Réceptionniste IA générée — prête à tester et à envoyer.')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'La génération a échoué')
    } finally {
      isGeneratingAssistant.value = false
    }
  }

  watch(
    (): [number, number] => [props.prospect.id, props.openingId],
    ([prospectId, openingId]: [number, number]): void => {
      if (lookups.value[prospectId]?.openingId === openingId) {
        return
      }
      lookUpAssistant(prospectId, openingId)
    },
    { immediate: true },
  )

  return { prospectAssistant, assistantDemoUrl, isGeneratingAssistant, generateAssistant }
}
