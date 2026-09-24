import { ApiClient } from '~/services/api'
import type {
  AiAssistantConversationsResponse,
  AiAssistantLeadsResponse,
  AiAssistantListResponse,
  AiAssistantSummary,
  AiAssistantUpdatePayload,
  AiAssistantVideoContext,
  AssistantSubscription,
  AssistantSubscriptionListResponse,
} from '~/types/AiAssistant'

const BASE_URL: string = '/api/v1/ai-assistants'

/** Generate and manage the AI assistants a user sells to prospects. */
export class AiAssistantService {
  /**
   * Generate an assistant for one of the user's prospects.
   *
   * @param prospectId - The prospect to generate the assistant for.
   * @returns The created assistant.
   */
  static create(prospectId: number): Promise<AiAssistantSummary> {
    return ApiClient.post<AiAssistantSummary>(BASE_URL, { prospect_id: prospectId })
  }

  /**
   * List the current user's assistants, newest first.
   *
   * @returns The user's assistants.
   */
  static list(): Promise<AiAssistantListResponse> {
    return ApiClient.get<AiAssistantListResponse>(BASE_URL)
  }

  /**
   * Fetch the assistant generated for one prospect, if any.
   *
   * @param prospectId - The prospect to look up.
   * @returns The prospect's assistant, or null when none exists.
   */
  static async getForProspect(prospectId: number): Promise<AiAssistantSummary | null> {
    const response: AiAssistantListResponse = await ApiClient.get<AiAssistantListResponse>(
      `${BASE_URL}?prospect_id=${prospectId}`,
    )
    return response.assistants[0] ?? null
  }

  /**
   * List the leads captured across the user's assistants, newest first.
   *
   * @returns The captured leads.
   */
  static listConversations(assistantId: number): Promise<AiAssistantConversationsResponse> {
    return ApiClient.get<AiAssistantConversationsResponse>(`${BASE_URL}/${assistantId}/conversations`)
  }

  /**
   * List the leads captured across the user's assistants, newest first.
   *
   * @returns The captured leads.
   */
  static listLeads(): Promise<AiAssistantLeadsResponse> {
    return ApiClient.get<AiAssistantLeadsResponse>(`${BASE_URL}/leads`)
  }

  /**
   * Edit one of the user's assistants (name, persona, languages, accent).
   *
   * @param assistantId - The assistant to edit.
   * @param payload - The fields to change.
   * @returns The updated assistant.
   */
  static update(assistantId: number, payload: AiAssistantUpdatePayload): Promise<AiAssistantSummary> {
    return ApiClient.patch<AiAssistantSummary>(`${BASE_URL}/${assistantId}`, payload)
  }

  /**
   * Rebuild an assistant's knowledge from its prospect's latest data. Branding and persona
   * (name, tone, languages, accent) and the public link are preserved.
   *
   * @param assistantId - The assistant to regenerate.
   * @returns The refreshed assistant.
   */
  static regenerate(assistantId: number): Promise<AiAssistantSummary> {
    return ApiClient.post<AiAssistantSummary>(`${BASE_URL}/${assistantId}/regenerate`, {})
  }

  /**
   * Start generating the assistant's prospection video (webcam speech + a recording of the widget).
   *
   * @param assistantId - The assistant to make a video for.
   * @returns The assistant with its video generation started.
   */
  static generateVideo(assistantId: number): Promise<AiAssistantSummary> {
    return ApiClient.post<AiAssistantSummary>(`${BASE_URL}/${assistantId}/video`, {})
  }

  /**
   * Fetch the context the desktop sidecar needs to build the assistant video locally.
   *
   * @param assistantId - The assistant to render.
   * @returns The demo url, presenter timings and output size.
   */
  static getVideoContext(assistantId: number): Promise<AiAssistantVideoContext> {
    return ApiClient.get<AiAssistantVideoContext>(`${BASE_URL}/${assistantId}/video-context`)
  }

  /**
   * Upload a desktop-produced FINAL video bundle (zip: video.mp4 + thumbnail.jpg).
   *
   * The sidecar does the whole montage locally; the API just stores it and marks the assistant
   * ready. Multipart, so it bypasses the JSON api client.
   * @param assistantId - The assistant the video belongs to.
   * @param bundle - The zip produced by the sidecar.
   * @returns The updated assistant.
   * @throws When the upload fails (message from the API when available).
   */
  static async uploadFinalVideo(assistantId: number, bundle: Blob): Promise<AiAssistantSummary> {
    const userStore: ReturnType<typeof useUserStore> = useUserStore()
    const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
    const formData: FormData = new FormData()
    formData.append('file', bundle, `${assistantId}-video.zip`)
    const response: Response = await fetch(`${config.public.apiBase}${BASE_URL}/${assistantId}/video-final`, {
      method: 'POST',
      headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
      body: formData,
    })
    if (!response.ok) {
      const errorText: string = await response.text().catch(() => '')
      let errorMessage: string = `Envoi de la vidéo échoué : ${response.statusText}`
      if (errorText) {
        try {
          errorMessage = (JSON.parse(errorText).detail as string) || errorMessage
        } catch {
          errorMessage = errorText
        }
      }
      throw new Error(errorMessage)
    }
    return (await response.json()) as AiAssistantSummary
  }

  /**
   * Delete the assistant's generated video and reset its state.
   *
   * @param assistantId - The assistant whose video to clear.
   * @returns The assistant with its video state reset.
   */
  static clearVideo(assistantId: number): Promise<AiAssistantSummary> {
    return ApiClient.delete<AiAssistantSummary>(`${BASE_URL}/${assistantId}/video`)
  }

  /**
   * The permanent subscription link to send a client: each click opens a fresh Stripe Checkout.
   *
   * @param assistantId - The assistant being sold.
   * @param interval - `month` (mensuel) or `year` (annuel).
   * @returns The link to send.
   */
  static getSubscriptionLink(assistantId: number, interval: 'month' | 'year'): Promise<{ url: string }> {
    return ApiClient.get<{ url: string }>(`${BASE_URL}/${assistantId}/subscription/link?interval=${interval}`)
  }

  /**
   * List the caller's assistant subscriptions + the headline KPIs (active count, MRR).
   * @returns The subscriptions with the active count and monthly recurring revenue.
   */
  static listSubscriptions(): Promise<AssistantSubscriptionListResponse> {
    return ApiClient.get<AssistantSubscriptionListResponse>(`${BASE_URL}/subscriptions`)
  }

  /**
   * Cancel a subscription (immediately, on Stripe + locally).
   * @param subscriptionId - The subscription to cancel.
   * @returns The updated subscription.
   */
  static cancelSubscription(subscriptionId: number): Promise<AssistantSubscription> {
    return ApiClient.post<AssistantSubscription>(`${BASE_URL}/subscriptions/${subscriptionId}/cancel`, {})
  }

  /**
   * Refund a subscription's latest payment (« satisfait-remboursé »).
   * @param subscriptionId - The subscription to refund.
   * @returns Nothing.
   */
  static async refundSubscription(subscriptionId: number): Promise<void> {
    await ApiClient.post(`${BASE_URL}/subscriptions/${subscriptionId}/refund`, {})
  }

  /**
   * Soft-delete one of the user's assistants.
   *
   * @param assistantId - The assistant to remove.
   * @returns Nothing.
   */
  static async remove(assistantId: number): Promise<void> {
    await ApiClient.delete(`${BASE_URL}/${assistantId}`)
  }
}
