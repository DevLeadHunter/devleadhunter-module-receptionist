import type { ClientSpaceNavItem } from '~/types/ClientSpaceNavigation'

/** The four sections of the client space, in the order of the tab bar and the sidebar. */
export const CLIENT_SPACE_NAV_ITEMS: ClientSpaceNavItem[] = [
  { section: 'home', label: 'Accueil', icon: 'house' },
  { section: 'requests', label: 'Demandes', icon: 'inbox' },
  { section: 'agenda', label: 'Agenda', icon: 'calendar' },
  { section: 'settings', label: 'Réglages', icon: 'sliders-horizontal' },
]
