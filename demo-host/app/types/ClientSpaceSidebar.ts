import type { ClientSpaceSection } from '~/types/ClientSpaceNavigation'

/** Props of the client-space sidebar (wide screens). */
export type ClientSpaceSidebarProps = {
  businessName: string
  section: ClientSpaceSection
  pendingCount: number
  assistantName: string
  portraitUrl: string
  portraitFallbackUrl: string
}

/** Events of the ClientSpaceSidebar component. */
export type ClientSpaceSidebarEmits = {
  navigate: [section: ClientSpaceSection]
  'open-assistant': []
  'open-help': []
}
