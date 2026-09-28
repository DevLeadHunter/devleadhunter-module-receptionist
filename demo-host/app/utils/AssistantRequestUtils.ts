import type {
  AssistantAppointmentSlots,
  AssistantChatReply,
  AssistantChatRequestBody,
  AssistantLeadReply,
  AssistantLeadRequestBody,
  AssistantPhotoReply,
} from '~/types/AiAssistant'
import type { AssistantRequestFailure } from '~/types/AssistantRequest'
import {
  ASSISTANT_FIRST_BYTE_TIMEOUT_MS,
  ASSISTANT_PHOTO_TIMEOUT_MS,
  ASSISTANT_REPLY_TIMEOUT_MS,
} from '~/constants/AssistantWidgetLimits'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'

/** The widget's calls to its assistant's public endpoints, each bounded in time and never retried; why one failed. */
export class AssistantRequestUtils {
  /**
   * The assistant's whole reply, asked without streaming.
   * @param endpoint - The assistant's public endpoint.
   * @param body - The chat request.
   * @returns The reply.
   * @throws The `$fetch` error when the call fails or times out.
   */
  static async fetchChatReply(endpoint: string, body: AssistantChatRequestBody): Promise<AssistantChatReply> {
    return await $fetch<AssistantChatReply>(`${endpoint}/chat`, {
      method: 'POST',
      body,
      timeout: ASSISTANT_REPLY_TIMEOUT_MS,
      retry: 0,
    })
  }

  /**
   * What the appointment panel offers: the agenda's free slots, or open half-days.
   * @param endpoint - The assistant's public endpoint.
   * @param after - The last free slot shown, to get the next ones (agenda only).
   * @returns The offer.
   * @throws The `$fetch` error when the call fails or times out.
   */
  static async fetchAppointmentSlots(endpoint: string, after: string | null): Promise<AssistantAppointmentSlots> {
    return await $fetch<AssistantAppointmentSlots>(`${endpoint}/appointment-slots`, {
      query: after ? { after } : {},
      timeout: ASSISTANT_FIRST_BYTE_TIMEOUT_MS,
      retry: 0,
    })
  }

  /**
   * Send the visitor's details, which the API turns into a request.
   * @param endpoint - The assistant's public endpoint.
   * @param body - The details, the appointment picked and the session.
   * @returns The API's answer (the booked start, when booked in the agenda).
   * @throws The `$fetch` error when the call fails, times out or is refused.
   */
  static async sendLead(endpoint: string, body: AssistantLeadRequestBody): Promise<AssistantLeadReply> {
    return await $fetch<AssistantLeadReply>(`${endpoint}/lead`, {
      method: 'POST',
      body,
      timeout: ASSISTANT_FIRST_BYTE_TIMEOUT_MS,
      retry: 0,
    })
  }

  /**
   * Send a photo for a quote.
   * @param endpoint - The assistant's public endpoint.
   * @param form - The photo, the session, the language and the internal flag.
   * @returns What the assistant says of the photo.
   * @throws The `$fetch` error when the call fails, times out or is refused.
   */
  static async sendPhoto(endpoint: string, form: FormData): Promise<AssistantPhotoReply> {
    return await $fetch<AssistantPhotoReply>(`${endpoint}/photo`, {
      method: 'POST',
      body: form,
      timeout: ASSISTANT_PHOTO_TIMEOUT_MS,
      retry: 0,
    })
  }

  /**
   * Why a call failed, from what `$fetch` threw.
   * @param error - The error.
   * @returns The failure the visitor is told about.
   */
  static failureOf(error: unknown): AssistantRequestFailure {
    return AssistantRequestUtils.failureOfStatus(ApiRefusalUtils.status(error))
  }

  /**
   * Why a call failed, from its HTTP status.
   * @param status - The status, undefined when no answer came (offline, timed out).
   * @returns The failure the visitor is told about.
   */
  static failureOfStatus(status: number | undefined): AssistantRequestFailure {
    if (status === undefined) return 'network'
    if (status === 429) return 'rate-limited'
    if (status === 404) return 'unavailable'
    return 'server'
  }
}
