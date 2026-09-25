import { ApiClient } from '~/services/api'
import type {
  AiAssistantClientLink,
  AiAssistantConversationsResponse,
  AiAssistantListResponse,
  AiAssistantRequestItem,
  AiAssistantRequestsResponse,
  AiAssistantRequestStatus,
  AiAssistantRequestUpdatePayload,
  AiAssistantSummary,
  AiAssistantUpdatePayload,
  AiAssistantVideoContext,
  AssistantSubscription,
  AssistantSubscriptionListResponse,
} from '~/types/AiAssistant'
import type { AiAssistantDocumentItem, AiAssistantSources, AiAssistantSourcesUpdate } from '~/types/AiAssistantSources'
import type { ApiErrorBody } from '~/types/Api'

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
   * List the latest conversations visitors had with one of the user's assistants.
   *
   * @param assistantId - The assistant whose journal to read.
   * @returns The 20 latest conversations, newest first.
   */
  static listConversations(assistantId: number): Promise<AiAssistantConversationsResponse> {
    return ApiClient.get<AiAssistantConversationsResponse>(`${BASE_URL}/${assistantId}/conversations`)
  }

  /**
   * What an assistant reads: its website pages, its Google listing, its documents.
   *
   * @param assistantId - The assistant.
   * @returns Its sources and the last website read.
   */
  static getSources(assistantId: number): Promise<AiAssistantSources> {
    return ApiClient.get<AiAssistantSources>(`${BASE_URL}/${assistantId}/sources`)
  }

  /**
   * Switch the website or the Google listing on or off.
   *
   * @param assistantId - The assistant.
   * @param update - The switches to change.
   * @returns The sources after the change.
   */
  static updateSources(assistantId: number, update: AiAssistantSourcesUpdate): Promise<AiAssistantSources> {
    return ApiClient.patch<AiAssistantSources>(`${BASE_URL}/${assistantId}/sources`, update)
  }

  /**
   * Read the business's website again now.
   *
   * @param assistantId - The assistant.
   * @returns The sources, with what changed.
   */
  static refreshWebsite(assistantId: number): Promise<AiAssistantSources> {
    return ApiClient.post<AiAssistantSources>(`${BASE_URL}/${assistantId}/sources/refresh`, {})
  }

  /**
   * Give the assistant a PDF to read.
   *
   * @param assistantId - The assistant.
   * @param file - The PDF.
   * @returns The stored document.
   * @throws Error carrying the API's explanation when the file is refused.
   */
  static async uploadDocument(assistantId: number, file: File): Promise<AiAssistantDocumentItem> {
    const formData: FormData = new FormData()
    formData.append('file', file, file.name)
    return AiAssistantService.postMultipart<AiAssistantDocumentItem>(
      `${BASE_URL}/${assistantId}/documents`,
      formData,
      'Envoi du document échoué',
    )
  }

  /**
   * Switch a document on or off.
   *
   * @param assistantId - The assistant.
   * @param documentId - The document.
   * @param enabled - Whether the assistant reads it.
   * @returns The document.
   */
  static setDocumentEnabled(
    assistantId: number,
    documentId: number,
    enabled: boolean,
  ): Promise<AiAssistantDocumentItem> {
    return ApiClient.patch<AiAssistantDocumentItem>(`${BASE_URL}/${assistantId}/documents/${documentId}`, { enabled })
  }

  /**
   * Delete a document and its file.
   *
   * @param assistantId - The assistant.
   * @param documentId - The document.
   * @returns A promise resolved once deleted.
   */
  static async deleteDocument(assistantId: number, documentId: number): Promise<void> {
    await ApiClient.delete(`${BASE_URL}/${assistantId}/documents/${documentId}`)
  }

  /**
   * List the requests visitors left across the user's assistants, newest first (the 300 latest).
   *
   * @param status - Only the requests in this status, when given.
   * @returns The requests and how many still wait for handling.
   */
  static listRequests(status?: AiAssistantRequestStatus): Promise<AiAssistantRequestsResponse> {
    const query: string = status ? `?status=${status}` : ''
    return ApiClient.get<AiAssistantRequestsResponse>(`${BASE_URL}/requests${query}`)
  }

  /**
   * Change a request's status (handled, dropped, new again) or note.
   *
   * @param requestId - The request to update.
   * @param payload - The fields to change.
   * @returns The updated request.
   */
  static updateRequest(requestId: number, payload: AiAssistantRequestUpdatePayload): Promise<AiAssistantRequestItem> {
    return ApiClient.patch<AiAssistantRequestItem>(`${BASE_URL}/requests/${requestId}`, payload)
  }

  /**
   * Edit one of the user's assistants (name, persona, languages, accent, owner alerts).
   *
   * @param assistantId - The assistant to edit.
   * @param payload - The fields to change.
   * @returns The updated assistant.
   */
  static update(assistantId: number, payload: AiAssistantUpdatePayload): Promise<AiAssistantSummary> {
    return ApiClient.patch<AiAssistantSummary>(`${BASE_URL}/${assistantId}`, payload)
  }

  /**
   * Sign a fresh client-space link for a sold assistant, and email it to the business when asked.
   *
   * @param assistantId - The sold assistant.
   * @param send - Email the link to the business's address.
   * @returns The link, its expiry and where it was sent.
   */
  static issueClientLink(assistantId: number, send: boolean): Promise<AiAssistantClientLink> {
    return ApiClient.post<AiAssistantClientLink>(`${BASE_URL}/${assistantId}/client-link`, { send })
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
    const formData: FormData = new FormData()
    formData.append('file', bundle, `${assistantId}-video.zip`)
    return AiAssistantService.postMultipart<AiAssistantSummary>(
      `${BASE_URL}/${assistantId}/video-final`,
      formData,
      'Envoi de la vidéo échoué',
    )
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

  /**
   * Send an authenticated multipart POST, which the JSON api client cannot carry.
   *
   * @param path - Path starting with `/api/`.
   * @param formData - The multipart body.
   * @param failureLabel - Start of the error message when the API sends no explanation, followed by the status text.
   * @returns The parsed response body.
   * @throws Error carrying the API `detail`, else the raw error body, else the label and the status text.
   */
  private static async postMultipart<T>(path: string, formData: FormData, failureLabel: string): Promise<T> {
    const userStore: ReturnType<typeof useUserStore> = useUserStore()
    const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
    const response: Response = await fetch(`${config.public.apiBase}${path}`, {
      method: 'POST',
      headers: userStore.token ? { Authorization: `Bearer ${userStore.token}` } : {},
      body: formData,
    })
    if (!response.ok) {
      const errorText: string = await response.text().catch((): string => '')
      let errorMessage: string = `${failureLabel} : ${response.statusText}`
      if (errorText) {
        try {
          const errorBody: ApiErrorBody = JSON.parse(errorText)
          if (typeof errorBody.detail === 'string' && errorBody.detail) errorMessage = errorBody.detail
        } catch {
          // Not the API answering (a proxy's HTML page, say): the status text is all we can show.
        }
      }
      throw new Error(errorMessage)
    }
    return (await response.json()) as T
  }
}
