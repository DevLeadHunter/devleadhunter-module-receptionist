import type { AiAssistantClientSubscriptionStatus } from '~/types/AiAssistantClientSpace'

/** Where the client's subscription stands, as the settings menu shows it (the subscription screen lowercases it). */
export const CLIENT_SPACE_SUBSCRIPTION_STATUS_LABELS: Record<AiAssistantClientSubscriptionStatus, string> = {
  incomplete: 'En attente',
  active: 'Actif',
  past_due: 'Paiement en attente',
  canceled: 'Résilié',
}
