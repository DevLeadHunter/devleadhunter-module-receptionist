import { useModuleStore } from '~/stores/moduleStore'

/** The receptionist pages belong to the AI module: reaching one by its address switches the sidebar to it. */
export default defineNuxtRouteMiddleware((): void => {
  useModuleStore().setModule('ai-assistant')
})
