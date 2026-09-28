import type { ComputedRef, Ref } from 'vue'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantContactDetails } from '~/types/AssistantChatContactForm'
import type { AssistantContactPrefill } from '~/types/AssistantContactPrefill'

export type UseAssistantLeadFormReturn = {
  isLeadFormOpen: ComputedRef<boolean>
  isSubmittingLead: Ref<boolean>
  leadPrefill: ComputedRef<AssistantContactPrefill>
  lastLeadSummary: Ref<AssistantLeadSummary | null>
  openLeadForm: () => void
  cancelLeadForm: () => void
  submitLead: (details: AssistantContactDetails) => Promise<void>
}
