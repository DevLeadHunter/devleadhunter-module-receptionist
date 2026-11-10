import type { RouteLocationNormalized } from 'vue-router'
import { useModuleStore } from '~/stores/moduleStore'
import { ASSISTANT_MODULE_KEY, ASSISTANT_SECTION_PATH } from '../constants/assistantModule'

/** Sends to the dashboard while the module is off; a page of its own section also switches the sidebar to it. */
export default defineNuxtRouteMiddleware(async (to: RouteLocationNormalized) => {
  const moduleStore: ReturnType<typeof useModuleStore> = useModuleStore()
  if (import.meta.client && !(await moduleStore.isModuleEnabled(ASSISTANT_MODULE_KEY))) {
    return navigateTo('/dashboard')
  }
  const isModuleSectionPage: boolean =
    to.path === ASSISTANT_SECTION_PATH || to.path.startsWith(`${ASSISTANT_SECTION_PATH}/`)

  if (isModuleSectionPage) {
    moduleStore.setModule(ASSISTANT_MODULE_KEY)
  }
})
