import type { AiAssistantRequestStatus, AiAssistantRequestType, AiAssistantSummary } from '~/types/AiAssistant'
import { daysUntil } from '~/utils/date'

/** French label of each assistant status. */
const STATUS_LABELS: Record<string, string> = {
  pending: 'En préparation',
  provisioning: 'En préparation',
  active: 'Démo en ligne',
  unavailable: 'Indisponible',
  expired: 'Expiré',
  failed: 'Échec',
  delivered: 'Vendu',
}

/** French label of each request type. */
export const REQUEST_TYPE_LABELS: Record<AiAssistantRequestType, string> = {
  question: 'Question',
  quote: 'Devis',
  appointment: 'Rendez-vous',
  urgent: 'Urgence',
  other: 'Autre',
}

/** French label of each request status. */
export const REQUEST_STATUS_LABELS: Record<AiAssistantRequestStatus, string> = {
  new: 'À traiter',
  handled: 'Traitée',
  dropped: 'Sans suite',
}

/**
 * The French label of an assistant status, or the raw status for an unknown one.
 * @param status - The status as the API returns it.
 * @returns The label.
 */
export function assistantStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

/**
 * Where a demo stands in its life: waiting for its first send, counting down, sold, or gone.
 * @param assistant - The assistant.
 * @returns A short French label.
 */
export function assistantLifetimeLabel(assistant: AiAssistantSummary): string {
  if (assistant.status === 'delivered') return 'En service chez le client'
  if (assistant.status !== 'active') return assistantStatusLabel(assistant.status)
  if (!assistant.demo_link_sent_at || !assistant.expires_at) return "En attente d'envoi"
  return `Expire dans ${daysUntil(assistant.expires_at)} j`
}

/**
 * Append the internal marker so opening a demo from the dashboard never pollutes its analytics.
 * @param demoUrl - The assistant's public demo URL.
 * @returns The URL carrying `?internal=1`.
 */
export function demoUrlWithInternal(demoUrl: string): string {
  return demoUrl.includes('?') ? `${demoUrl}&internal=1` : `${demoUrl}?internal=1`
}
