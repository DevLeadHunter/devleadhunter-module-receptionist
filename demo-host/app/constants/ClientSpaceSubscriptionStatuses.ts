import type { AiAssistantClientSubscriptionStatus } from '~/types/AiAssistantClientSpace'

export const CLIENT_SPACE_SUBSCRIPTION_STATUS_LABELS: Record<AiAssistantClientSubscriptionStatus, string> = {
  incomplete: 'En attente',
  active: 'Actif',
  past_due: 'Paiement en attente',
  canceled: 'Résilié',
}
