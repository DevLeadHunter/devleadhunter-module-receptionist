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
