import type { Ref } from 'vue'
import type { AiAssistantClientCalendarUpdate } from '~/types/AiAssistantClientSpace'

export type UseClientSpaceCalendarReturn = {
  isCalendarBusy: Ref<boolean>
  calendarError: Ref<string | null>
  hasSavedCalendar: Ref<boolean>
  connectCalendar: () => Promise<void>
  saveCalendar: (update: AiAssistantClientCalendarUpdate) => Promise<void>
  disconnectCalendar: () => Promise<void>
  clearCalendarFeedback: () => void
}
