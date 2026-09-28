import type { AiAssistantClientSubscription } from '~/types/AiAssistantClientSpace'

export type ClientSpaceSubscriptionProps = {
  subscription: AiAssistantClientSubscription | null
  isOpeningBillingPortal: boolean
  billingPortalError: string | null
  readOnly: boolean
}

export type ClientSpaceSubscriptionEmits = {
  'open-billing-portal': []
}
