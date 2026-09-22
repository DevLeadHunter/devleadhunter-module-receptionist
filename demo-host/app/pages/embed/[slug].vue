<template>
  <AssistantChat v-if="assistant" :config="assistant" />
</template>

<script lang="ts" setup>
import type { ComputedRef } from 'vue'
import { computed, onMounted } from 'vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { useDemoTracking } from '~/composables/useDemoTracking'

definePageMeta({ layout: false })

const route: ReturnType<typeof useRoute> = useRoute()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
const slug: ComputedRef<string> = computed((): string => String(route.params.slug ?? ''))

const { data: assistant }: Awaited<ReturnType<typeof useAsyncData<AiAssistantConfig | null | undefined>>> =
  await useAsyncData<AiAssistantConfig | null>(
    () => `assistant-embed-${slug.value}`,
    async (): Promise<AiAssistantConfig | null> => {
      try {
        return await $fetch<AiAssistantConfig>(`${config.public.apiBase}/api/v1/ai-assistants/public/${slug.value}`)
      } catch {
        return null
      }
    },
  )

const { init: initTracking }: ReturnType<typeof useDemoTracking> = useDemoTracking()

onMounted((): void => {
  const current: AiAssistantConfig | null | undefined = assistant.value
  if (!current) return
  void initTracking(current.slug, current.status, null, DemoBeaconUtils.channelFromQuery(route.query.src))
})

useHead({
  htmlAttrs: { style: 'background: transparent;' },
  bodyAttrs: { style: 'background: transparent;' },
})
</script>

<style>
html,
body {
  background: transparent !important;
}
</style>
