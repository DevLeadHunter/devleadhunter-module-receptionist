import type {
  AiAssistantMailboxConnection,
  AiAssistantRequestStatus,
  AiAssistantRequestType,
  AiAssistantStartStep,
  AiAssistantSummary,
  AssistantSubscriptionStatus,
} from '~/types/AiAssistant'
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

export const SUBSCRIPTION_STATUS_LABELS: Record<AssistantSubscriptionStatus, string> = {
  incomplete: 'En attente',
  active: 'Actif',
  past_due: 'Paiement en retard',
  canceled: 'Annulé',
}

const MAILBOX_STATUS_LABELS: Record<AiAssistantMailboxConnection, string> = {
  disabled: 'Non activée',
  unavailable: 'Non configurée sur le serveur',
  disconnected: 'En attente de connexion',
  connected: 'Connectée',
  error: 'À reconnecter',
}

/** Each « Pour démarrer » step as the seller names it when calling the business. */
const START_STEP_LABELS: Record<AiAssistantStartStep, string> = {
  alert_phone: "Mobile d'alerte",
  google_profile_or_website: 'Adresse sur la fiche Google ou ligne sur le site',
  google_calendar: 'Agenda Google',
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
 * Where a receptionist's Gmail mailbox stands, with the connected address (« Connectée : garage@gmail.com »).
 * @param assistant - The receptionist.
 * @returns A short French label.
 */
export function mailboxStatusLabel(assistant: AiAssistantSummary): string {
  const label: string = MAILBOX_STATUS_LABELS[assistant.mailbox_status]
  if (assistant.mailbox_status === 'connected' && assistant.mailbox_address) {
    return `${label} : ${assistant.mailbox_address}`
  }
  return label
}

/**
 * A language code as the widget knows it: Luxembourgish, first stored as « lu », is « lb ».
 * @param code - The code as stored on an assistant, a request or a conversation.
 * @returns The code, « lb » for a stored « lu ».
 */
export function widgetLanguageCode(code: string): string {
  return code === 'lu' ? 'lb' : code
}

/**
 * A language code as the widget names it, in capitals (« DE », « LB » for a stored « lu »).
 * @param code - The code as stored on an assistant, a request or a conversation.
 * @returns The upper-case code.
 */
export function languageCodeLabel(code: string): string {
  return widgetLanguageCode(code).toUpperCase()
}

/**
 * An assistant's languages on one line, as the widget names them (« FR · EN · LB »).
 * @param languages - The codes as stored on the assistant.
 * @returns The upper-case codes joined by a middle dot.
 */
export function assistantLanguagesLabel(languages: string[]): string {
  return languages.map(languageCodeLabel).join(' · ')
}

/**
 * The « Pour démarrer » steps a sold assistant still misses, joined for one line (« Mobile d'alerte · Agenda Google »).
 * @param steps - The missing steps, as the API returns them.
 * @returns The labels joined by a middle dot.
 */
export function missingStartStepsLabel(steps: AiAssistantStartStep[]): string {
  return steps.map((step: AiAssistantStartStep): string => START_STEP_LABELS[step]).join(' · ')
}

/**
 * Append the internal marker so opening a demo from the dashboard never pollutes its analytics.
 * @param demoUrl - The assistant's public demo URL.
 * @returns The URL carrying `?internal=1`.
 */
export function demoUrlWithInternal(demoUrl: string): string {
  return demoUrl.includes('?') ? `${demoUrl}&internal=1` : `${demoUrl}?internal=1`
}
