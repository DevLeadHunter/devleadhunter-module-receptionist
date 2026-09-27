import type { AiAssistantOpeningHoursRow } from '~/types/AiAssistantPublicBusiness'

/** Props of a business's opening hours, one line a day. */
export type OpeningHoursListProps = {
  rows: AiAssistantOpeningHoursRow[]
}
