import type { ComputedRef, Ref } from 'vue'
import type { AssistantCapturedContact } from './AiAssistant'
import type { AssistantLeadSummary } from './AssistantChat'
import type { AssistantContactDetails } from './AssistantChatContactForm'
import type { AssistantContactPrefill } from './AssistantContactPrefill'

export type UseAssistantLeadFormReturn = {
  isLeadFormOpen: ComputedRef<boolean>
  isSubmittingLead: Ref<boolean>
  leadPrefill: ComputedRef<AssistantContactPrefill>
  lastLeadSummary: Ref<AssistantLeadSummary | null>
  openLeadForm: () => void
  cancelLeadForm: () => void
  submitLead: (details: AssistantContactDetails) => Promise<void>
  confirmCapturedContact: (captured: AssistantCapturedContact) => void
}
