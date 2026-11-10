import type { AiAssistantClientFaqEntry } from './AiAssistantClientSpace'

/** Props of the list of answers the business taught its receptionist. */
export type ClientSpaceLearnedAnswersProps = {
  faq: AiAssistantClientFaqEntry[]
  assistantName: string
}
