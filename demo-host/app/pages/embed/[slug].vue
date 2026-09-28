<template>
  <AssistantChat v-if="assistant" :assistant="assistant" :host-page="hostPage" />
</template>

<script lang="ts" setup>
import type { ComputedRef } from 'vue'
import { computed, onMounted } from 'vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantHostPage } from '~/types/AssistantDemoScript'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { useDemoTracking } from '~/composables/useDemoTracking'

definePageMeta({ layout: false })

const route: ReturnType<typeof useRoute> = useRoute()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()

const { data: assistant }: Awaited<ReturnType<typeof useAsyncData<AiAssistantConfig | null>>> = await useAsyncData(
  (): string => `assistant-embed-${routeSlug()}`,
  async (): Promise<AiAssistantConfig | null> => {
    try {
      return await $fetch<AiAssistantConfig>(`${config.public.apiBase}/api/v1/ai-assistants/public/${routeSlug()}`)
    } catch {
      return null
    }
  },
)

const { init: initTracking }: ReturnType<typeof useDemoTracking> = useDemoTracking()

/** The client's page the loader embedded the widget on (its path and title), for the greeting. */
const hostPage: ComputedRef<AssistantHostPage | null> = computed((): AssistantHostPage | null => {
  const path: string = String(route.query.page ?? '')
  const title: string = String(route.query.title ?? '')
  return path || title ? { path, title } : null
})

/**
 * The assistant's slug, as the address names it.
 * @returns The slug.
 */
function routeSlug(): string {
  return String(route.params.slug ?? '')
}

onMounted((): void => {
  const current: AiAssistantConfig | null | undefined = assistant.value
  if (!current) {
    // Nothing to show (unknown slug, demo expired): the loader removes its iframe from the host page.
    window.parent.postMessage({ type: 'dlh-assistant-unavailable' }, '*')
    return
  }
  initTracking(current.slug, current.status, null, DemoBeaconUtils.channelFromQuery(route.query.src), 'assistant')
})
</script>

<style>
html,
body {
  background: transparent !important;
}
</style>
