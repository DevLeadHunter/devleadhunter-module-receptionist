import type { AiAssistantRequestItem } from '~/types/AiAssistant'

/** Props of the drawer showing one visitor request, its conversation and the owner's actions. */
export type UiAssistantRequestDrawerProps = {
  open: boolean
  request: AiAssistantRequestItem | null
  showBack: boolean
}

/** Events the request drawer emits; `updated` carries the request as the API returned it. */
export type UiAssistantRequestDrawerEmits = {
  close: []
  back: []
  updated: [request: AiAssistantRequestItem]
}
