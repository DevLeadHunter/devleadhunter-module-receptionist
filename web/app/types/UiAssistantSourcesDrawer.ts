import type { AiAssistantSummary } from '~/types/AiAssistant'

/** Props of the drawer listing what an assistant reads (website, Google listing, documents). */
export type UiAssistantSourcesDrawerProps = {
  open: boolean
  assistant: AiAssistantSummary | null
  showBack: boolean
}

/** Events the sources drawer emits. */
export type UiAssistantSourcesDrawerEmits = {
  close: []
  back: []
}
