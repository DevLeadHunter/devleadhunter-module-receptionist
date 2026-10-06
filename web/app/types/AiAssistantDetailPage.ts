/** One counter of the assistant detail page. */
export type AiAssistantDetailStat = {
  label: string
  value: string | number
  icon: string
}

/** One line of the « Informations » card of the receptionist's « Plus » page. */
export type AiAssistantInformationRow = {
  label: string
  value: string
}

/** The tools of the receptionist's atelier bar. */
export type AiAssistantAtelierToolKey = 'identite' | 'reponses' | 'demandes' | 'alertes' | 'video' | 'plus'
