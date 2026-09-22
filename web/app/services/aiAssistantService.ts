import { ApiClient } from '~/services/api'
import type { AiAssistantListResponse, AiAssistantSummary } from '~/types/AiAssistant'

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
   * Soft-delete one of the user's assistants.
   *
   * @param assistantId - The assistant to remove.
   * @returns Nothing.
   */
  static async remove(assistantId: number): Promise<void> {
    await ApiClient.delete(`${BASE_URL}/${assistantId}`)
  }
}
