/** One counter of the assistant detail page. */
export type AiAssistantDetailStat = {
  label: string
  value: string | number
  icon: string
}

/** The tools of the receptionist's atelier bar. */
export type AiAssistantAtelierToolKey = 'identite' | 'reponses' | 'demandes' | 'alertes' | 'video' | 'plus'
