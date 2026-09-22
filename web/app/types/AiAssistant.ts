/** An AI assistant generated for a prospect, as seen by its owner. */
export interface AiAssistantSummary {
  id: number
  slug: string
  prospect_id: number | null
  business_name: string
  assistant_name: string
  languages: string[]
  status: string
  demo_url: string
  embed_snippet: string
  created_at: string
}

/** The current user's assistants. */
export interface AiAssistantListResponse {
  assistants: AiAssistantSummary[]
}

/** One lead a visitor left through an assistant, as seen by its owner. */
export type AiAssistantLead = {
  id: number
  assistant_id: number
  prospect_id: number | null
  business_name: string
  name: string
  contact: string
  need: string | null
  language: string | null
  created_at: string
}

/** The leads captured across the current user's assistants. */
export type AiAssistantLeadsResponse = {
  leads: AiAssistantLead[]
}
