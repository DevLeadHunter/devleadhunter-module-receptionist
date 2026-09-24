import type { AiAssistantClientReport } from '~/types/AiAssistantClientSpace'

/** Props of the client-space monthly report card. */
export type ClientSpaceReportProps = {
  report: AiAssistantClientReport | null
  assistantName: string
}

/** One figure of the report grid, over its label. */
export type ClientSpaceReportFigure = {
  value: string
  label: string
}
