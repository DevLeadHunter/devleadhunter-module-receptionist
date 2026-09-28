import type { Ref } from 'vue'
import type { AiAssistantClientRequestOutcome } from '~/types/AiAssistantClientSpace'

export type ClientSpaceRequestAction = 'handled' | 'dropped' | 'outcome'

export type UseClientSpaceRequestsReturn = {
  busyRequestId: Ref<number | null>
  requestError: Ref<string | null>
  isQuestionBusy: Ref<boolean>
  questionError: Ref<string | null>
  markHandled: (requestId: number) => Promise<void>
  markDropped: (requestId: number) => Promise<void>
  setOutcome: (requestId: number, outcome: AiAssistantClientRequestOutcome | null) => Promise<void>
  answerQuestion: (question: string, answer: string) => Promise<boolean>
  dismissQuestion: (index: number) => Promise<boolean>
}
