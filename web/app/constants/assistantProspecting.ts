import type { ProspectListModuleOptions, ProspectSearchModuleOptions } from '~/types/ProspectingModuleOptions'
import { ASSISTANT_MODULE_KEY } from './assistantModule'
import { AssistantTradeWaves } from '../services/assistantTradeWaves'

/** « Mes prospects » for the receptionist: pros with or without a site, the strongest inbound demand first. */
export const ASSISTANT_PROSPECT_LIST_OPTIONS: ProspectListModuleOptions = {
  moduleKey: ASSISTANT_MODULE_KEY,
  defaultWebsiteFilter: 'all',
  defaultSortOrder: 'demand',
  showsInboundDemand: true,
  hasChatWebsiteFilters: true,
  canBulkScanWebsites: true,
}

/** A new search for the receptionist: pros with or without a site, among its target verticals wave by wave. */
export const ASSISTANT_PROSPECT_SEARCH_OPTIONS: ProspectSearchModuleOptions = {
  moduleKey: ASSISTANT_MODULE_KEY,
  isOnlyWithoutWebsiteByDefault: false,
  tradeInputPlaceholder: 'Couvreur, carrosserie…',
  withWebsitesHint:
    'La réceptionniste vit sur sa propre page : avec ou sans site, un pro qui reçoit des demandes est une cible.',
  loadTradeWaves: AssistantTradeWaves.load,
}
