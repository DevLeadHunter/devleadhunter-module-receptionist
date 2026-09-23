/** Props of the assistant sales-page « me contacter » banner. */
export type AssistantContactBannerProps = {
  slug: string
  businessName: string
  ownerName: string | null
  ownerPhotoUrl: string | null
  ownerPhone: string | null
  ownerEmail: string | null
  status: string
  accentColor: string | null
}

/** The banner is either a discreet pill, the open message card, or the sent confirmation. */
export type AssistantContactBannerState = 'collapsed' | 'open' | 'sent'
