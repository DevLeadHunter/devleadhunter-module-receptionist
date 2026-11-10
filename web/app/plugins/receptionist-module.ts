import type { ProspectDrawerSectionContext } from '~/types/ProspectDrawerExtension'
import type { AiAssistantRequestItem, AssistantSubscription } from '../types/AiAssistant'
import type {
  AssistantConversationsDrawerEntry,
  AssistantRequestDrawerEntry,
  AssistantSourcesDrawerEntry,
  AssistantSubscriptionDrawerEntry,
} from '../types/AssistantDrawerStack'
import { defineAsyncComponent } from 'vue'
import { DashboardModuleRegistry } from '~/utils/dashboardModuleRegistry'
import { DesktopVideoSubjectRegistry } from '~/utils/desktopVideoSubjectRegistry'
import { DrawerKindRegistry } from '~/utils/drawerKindRegistry'
import { EmailVariables } from '~/utils/emailVariables'
import { PresenterVideoAdapterRegistry } from '~/utils/presenterVideoAdapterRegistry'
import { ProspectDrawerExtensionRegistry } from '~/utils/prospectDrawerExtensionRegistry'
import { ProspectingOptionsRegistry } from '~/utils/prospectingOptionsRegistry'
import { ProspectWebsite } from '~/utils/prospectWebsite'
import { SettingsNavRegistry } from '~/utils/settingsNavRegistry'
import { ASSISTANT_EMAIL_VARIABLES } from '../constants/assistantEmailVariables'
import { ASSISTANT_DASHBOARD_MODULE, ASSISTANT_MODULE_KEY } from '../constants/assistantModule'
import { ASSISTANT_PROSPECT_LIST_OPTIONS, ASSISTANT_PROSPECT_SEARCH_OPTIONS } from '../constants/assistantProspecting'
import { useAssistantDrawerChanges } from '../composables/useAssistantDrawerChanges'
import { ASSISTANT_DESKTOP_VIDEO_SUBJECT } from '../services/assistantDesktopVideoSubject'
import { ASSISTANT_PRESENTER_VIDEO_ADAPTER } from '../services/assistantPresenterVideoAdapter'

/** Plugs the receptionist into the core's registries: switcher, drawers, prospect drawer, prospecting, videos, emails. */
export default defineNuxtPlugin((): void => {
  DashboardModuleRegistry.register(ASSISTANT_DASHBOARD_MODULE)

  DrawerKindRegistry.register({
    kind: 'assistant-subscription',
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ui/SubscriptionDrawer.vue')),
    entryProps: (entry: AssistantSubscriptionDrawerEntry): Record<string, unknown> => ({
      subscription: entry.subscription,
    }),
    notifyChange: (subscription: AssistantSubscription): void => {
      useAssistantDrawerChanges().notifySubscriptionUpdated(subscription)
    },
  })
  DrawerKindRegistry.register({
    kind: 'assistant-conversations',
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ui/AssistantConversationsDrawer.vue')),
    entryProps: (entry: AssistantConversationsDrawerEntry): Record<string, unknown> => ({ assistant: entry.assistant }),
  })
  DrawerKindRegistry.register({
    kind: 'assistant-sources',
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ui/AssistantSourcesDrawer.vue')),
    entryProps: (entry: AssistantSourcesDrawerEntry): Record<string, unknown> => ({ assistant: entry.assistant }),
  })
  DrawerKindRegistry.register({
    kind: 'assistant-request',
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ui/AssistantRequestDrawer.vue')),
    entryProps: (entry: AssistantRequestDrawerEntry): Record<string, unknown> => ({ request: entry.request }),
    notifyChange: (request: AiAssistantRequestItem): void => {
      useAssistantDrawerChanges().notifyAssistantRequestUpdated(request)
    },
  })

  ProspectDrawerExtensionRegistry.registerSection({
    key: 'assistant-receptionist',
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ai-assistants/AssistantProspectSection.vue')),
    isShown: (context: ProspectDrawerSectionContext): boolean => context.activeModuleKey !== ASSISTANT_MODULE_KEY,
  })
  ProspectDrawerExtensionRegistry.registerSection({
    key: 'assistant-website-equipment',
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ai-assistants/ProspectWebsiteEquipmentSection.vue')),
    isShown: (context: ProspectDrawerSectionContext): boolean => ProspectWebsite.hasWorkingWebsite(context.prospect),
  })
  ProspectDrawerExtensionRegistry.registerPrimaryAction({
    moduleKey: ASSISTANT_MODULE_KEY,
    component: defineAsyncComponent(() => import('../components/ai-assistants/AssistantProspectPrimaryAction.vue')),
  })

  ProspectingOptionsRegistry.registerListOptions(ASSISTANT_PROSPECT_LIST_OPTIONS)
  ProspectingOptionsRegistry.registerSearchOptions(ASSISTANT_PROSPECT_SEARCH_OPTIONS)

  PresenterVideoAdapterRegistry.register(ASSISTANT_PRESENTER_VIDEO_ADAPTER)

  DesktopVideoSubjectRegistry.register(ASSISTANT_DESKTOP_VIDEO_SUBJECT)

  EmailVariables.registerModuleVariables(ASSISTANT_MODULE_KEY, ASSISTANT_EMAIL_VARIABLES)

  SettingsNavRegistry.register({
    moduleKey: ASSISTANT_MODULE_KEY,
    groupHeading: 'Compte',
    entry: { to: '/dashboard/settings/receptionist', label: 'Réceptionniste IA', icon: 'i-lucide-bot' },
  })
})
