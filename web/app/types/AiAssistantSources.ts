/** A page of the business's website the assistant read. */
export type AiAssistantSourcePage = {
  url: string
  title: string | null
  chars: number
}

/** The last read of the website: when, how many pages, what changed since the one before, or why it failed. */
export type AiAssistantWebsiteSync = {
  at: string | null
  pages: number
  added: string[]
  removed: string[]
  changed: string[]
  error: string | null
}

/** A document the business gave its assistant; `truncated` when its text was cut to its bound. */
export type AiAssistantDocumentItem = {
  id: number
  name: string
  pages: number
  size_bytes: number
  chars: number
  truncated: boolean
  enabled: boolean
  url: string | null
  created_at: string
}

/** Everything an assistant reads, and what can be switched off. */
export type AiAssistantSources = {
  website_url: string | null
  site_enabled: boolean
  listing_enabled: boolean
  pages: AiAssistantSourcePage[]
  sync: AiAssistantWebsiteSync | null
  listing_facts: string[]
  documents: AiAssistantDocumentItem[]
  max_documents: number
}

/** Switch the website or the Google listing on or off (partial). */
export type AiAssistantSourcesUpdate = {
  site_enabled?: boolean
  listing_enabled?: boolean
}
