import type { AssistantSubscription } from '~/types/AiAssistant'

/** Props of the assistant-subscription detail drawer. */
export type UiSubscriptionDrawerProps = {
  open: boolean
  subscription: AssistantSubscription | null
  showBack: boolean
}

/** Events the subscription drawer emits (the host turns `updated` into a store broadcast). */
export type UiSubscriptionDrawerEmits = {
  close: []
  back: []
  updated: [subscription: AssistantSubscription]
}
