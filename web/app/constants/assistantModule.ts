import type { ProductModuleKey } from '~/types/ProductModule'
import type { DashboardModuleDefinition, UiSidebarGroup } from '~/types/UiSidebar'

/** The receptionist's key, as the API stores it (historical: already in `prospects.contacted_by_module`). */
export const ASSISTANT_MODULE_KEY: ProductModuleKey = 'ai-assistant'

/** The receptionist's own section of the dashboard: reaching one of its pages switches the sidebar to the module. */
export const ASSISTANT_SECTION_PATH: string = '/dashboard/ai-assistants'

/**
 * The receptionist's navigation: the same prospection base as the sites, but the deliverable is an embedded
 * receptionist (« Réceptionnistes IA ») instead of a demo site — so « Sites démo » and the site automation tunnel
 * drop out, the assistants and their captured leads come in, and the one-off « Ventes » becomes the recurring
 * « Abonnements ».
 */
const ASSISTANT_NAV_GROUPS: UiSidebarGroup[] = [
  {
    heading: 'Pilotage',
    links: [{ to: '/dashboard', label: 'Tableau de bord', icon: 'i-lucide-layout-dashboard' }],
  },
  {
    heading: 'Prospection',
    links: [
      { to: '/dashboard/my-prospects', label: 'Mes prospects', icon: 'i-lucide-users', counterKey: 'pendingLeads' },
      { to: '/dashboard/coverage', label: 'Carte de prospection', icon: 'i-lucide-map' },
      { to: ASSISTANT_SECTION_PATH, label: 'Réceptionnistes IA', icon: 'i-lucide-bot' },
      { to: `${ASSISTANT_SECTION_PATH}/requests`, label: 'Demandes', icon: 'i-lucide-inbox' },
      { to: '/dashboard/campaigns', label: 'Campagnes', icon: 'i-lucide-megaphone' },
      { to: '/dashboard/emails', label: 'Suivi des emails', icon: 'i-lucide-send' },
      { to: '/dashboard/sms', label: 'Suivi des SMS', icon: 'i-lucide-message-square-text' },
      { to: '/dashboard/subscriptions', label: 'Abonnements', icon: 'i-lucide-repeat' },
    ],
  },
]

/** The receptionist in the module switcher, with the labels the core shows for its data. */
export const ASSISTANT_DASHBOARD_MODULE: DashboardModuleDefinition = {
  key: ASSISTANT_MODULE_KEY,
  label: 'Réceptionniste IA',
  icon: 'i-lucide-bot',
  home: ASSISTANT_SECTION_PATH,
  primaryCta: { label: 'Trouver des prospects', to: '/dashboard/search-prospects', icon: 'i-lucide-search' },
  navGroups: ASSISTANT_NAV_GROUPS,
  activityCategoryLabels: { assistant: 'Réceptionniste IA' },
  describeProspectsWithoutOffer: (prospectNames: string[]): string => {
    const several: boolean = prospectNames.length > 1
    return (
      `Pas encore en file d'attente (pas d'assistant IA actif) : ${prospectNames.join(', ')}. ` +
      `Génère ${several ? 'leurs assistants : ils rejoindront' : 'son assistant : il rejoindra'} la file à ${several ? 'leur' : 'sa'} position.`
    )
  },
}
