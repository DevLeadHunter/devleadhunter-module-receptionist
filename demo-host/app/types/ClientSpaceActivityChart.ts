import type { AiAssistantClientActivityDay } from '~/types/AiAssistantClientSpace'

/** Props of the client-space activity chart. */
export type ClientSpaceActivityChartProps = {
  /** The days to draw, oldest first. */
  days: AiAssistantClientActivityDay[]
}

/** One day of the chart, ready to draw: its bars' heights in % of the scale, its tooltip and its axis label. */
export type ClientSpaceActivityChartColumn = {
  day: string
  conversationsHeight: string
  requestsHeight: string
  tooltip: string
  axisLabel: string
  axisAlign: 'start' | 'center' | 'end'
}
