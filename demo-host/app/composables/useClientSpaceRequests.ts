import type { Ref } from 'vue'
import { ref } from 'vue'
import type {
  AiAssistantClientFaqResponse,
  AiAssistantClientRequest,
  AiAssistantClientRequestOutcome,
  AiAssistantClientRequestOutcomeUpdate,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import type { ClientSpaceRequestAction, UseClientSpaceRequestsReturn } from '~/types/UseClientSpaceRequests'

/**
 * The requests section's actions: requests called back, set aside or given an outcome, questions answered.
 * @param link - The client's link: the space to update and the API to call.
 * @returns What is in flight, what failed, and the actions.
 */
export function useClientSpaceRequests(link: UseClientSpaceLinkReturn): UseClientSpaceRequestsReturn {
  const busyRequestId: Ref<number | null> = ref(null)
  const requestError: Ref<string | null> = ref(null)
  const isQuestionBusy: Ref<boolean> = ref(false)
  const questionError: Ref<string | null> = ref(null)

  /**
   * Replace a request in the list with what the API returned, and keep the pending count right.
   * @param updated - The request as the API returned it.
   */
  function replaceRequest(updated: AiAssistantClientRequest): void {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current) return
    const wasPending: boolean = current.requests.some(
      (item: AiAssistantClientRequest): boolean => item.id === updated.id && item.status === 'new',
    )
    current.requests = current.requests.map((item: AiAssistantClientRequest): AiAssistantClientRequest =>
      item.id === updated.id ? updated : item,
    )
    if (wasPending && updated.status !== 'new') current.pending_count = Math.max(0, current.pending_count - 1)
  }

  /**
   * Change a request's status through the API and reflect it in the list.
   * @param requestId - The request.
   * @param action - What happened to it.
   * @param body - The outcome, for « outcome ».
   * @returns A promise resolved once the API answered.
   */
  async function changeRequest(
    requestId: number,
    action: ClientSpaceRequestAction,
    body?: AiAssistantClientRequestOutcomeUpdate,
  ): Promise<void> {
    if (!link.space.value || busyRequestId.value !== null) return
    busyRequestId.value = requestId
    requestError.value = null
    try {
      const updated: AiAssistantClientRequest = await $fetch<AiAssistantClientRequest>(
        `${link.endpoint.value}/requests/${requestId}/${action}`,
        { method: 'POST', body },
      )
      replaceRequest(updated)
    } catch (error: unknown) {
      requestError.value = link.failureMessage(
        error,
        'La demande n’a pas pu être mise à jour, réessayez dans un instant.',
      )
    } finally {
      busyRequestId.value = null
    }
  }

  /**
   * Mark a request called back.
   * @param requestId - The request.
   * @returns A promise resolved once the API answered.
   */
  async function markHandled(requestId: number): Promise<void> {
    await changeRequest(requestId, 'handled')
  }

  /**
   * Set a request aside: a test, spam, a duplicate.
   * @param requestId - The request.
   * @returns A promise resolved once the API answered.
   */
  async function markDropped(requestId: number): Promise<void> {
    await changeRequest(requestId, 'dropped')
  }

  /**
   * Say what became of a request called back: a client won, lost, or nothing yet.
   * @param requestId - The request.
   * @param outcome - The outcome, or null to clear it.
   * @returns A promise resolved once the API answered.
   */
  async function setOutcome(requestId: number, outcome: AiAssistantClientRequestOutcome | null): Promise<void> {
    await changeRequest(requestId, 'outcome', { outcome })
  }

  /**
   * Record the business's answer to a question the receptionist could not answer; both lists come back updated.
   * @param question - The question as it was asked.
   * @param answer - The answer to give from now on.
   * @returns True once the answer is recorded.
   */
  async function answerQuestion(question: string, answer: string): Promise<boolean> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isQuestionBusy.value) return false
    isQuestionBusy.value = true
    questionError.value = null
    try {
      const lists: AiAssistantClientFaqResponse = await $fetch<AiAssistantClientFaqResponse>(
        `${link.endpoint.value}/faq`,
        { method: 'POST', body: { question, answer } },
      )
      current.faq = lists.faq
      current.unanswered = lists.unanswered
      return true
    } catch (error: unknown) {
      if (!link.showExpiredOnUnauthorized(error)) {
        questionError.value = 'La réponse n’a pas pu être enregistrée, réessayez dans un instant.'
      }
      return false
    } finally {
      isQuestionBusy.value = false
    }
  }

  /**
   * Drop a question of the receptionist without answering it.
   * @param index - The question's position in the unanswered list.
   * @returns True once the question is gone.
   */
  async function dismissQuestion(index: number): Promise<boolean> {
    const current: AiAssistantClientSpace | null = link.space.value
    if (!current || isQuestionBusy.value) return false
    isQuestionBusy.value = true
    questionError.value = null
    try {
      await $fetch(`${link.endpoint.value}/unanswered/${index}`, { method: 'DELETE' })
      current.unanswered = current.unanswered.filter((_: unknown, position: number): boolean => position !== index)
      return true
    } catch (error: unknown) {
      if (!link.showExpiredOnUnauthorized(error)) {
        questionError.value = 'La question n’a pas pu être retirée, réessayez dans un instant.'
      }
      return false
    } finally {
      isQuestionBusy.value = false
    }
  }

  return {
    busyRequestId,
    requestError,
    isQuestionBusy,
    questionError,
    markHandled,
    markDropped,
    setOutcome,
    answerQuestion,
    dismissQuestion,
  }
}
