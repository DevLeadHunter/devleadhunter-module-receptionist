import type { ClientSpaceSection } from '~/types/ClientSpaceNavigation'

/** Props of the client-space tab bar (phones). */
export type ClientSpaceTabBarProps = {
  section: ClientSpaceSection
  pendingCount: number
}

/** Events of the ClientSpaceTabBar component. */
export type ClientSpaceTabBarEmits = {
  navigate: [section: ClientSpaceSection]
}
