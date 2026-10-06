<template>
  <div class="ia-page" :style="accentStyle">
    <p v-if="pending" class="ia-page__message">Chargement…</p>
    <div v-else-if="loadError" class="ia-page__message">
      <p>La page ne s'est pas chargée.</p>
      <button type="button" class="ia-page__retry" @click="refresh()">Réessayer</button>
    </div>
    <p v-else-if="!shownAssistant" class="ia-page__message ia-page__message--error">
      Cette page n'est plus disponible.
    </p>
    <template v-else-if="shownAssistant">
      <p v-if="isJustSubscribed" class="ia-page__notice" role="status">
        C'est fait : {{ shownAssistant.assistant_name }} est à vous. Le lien de votre espace arrive par e-mail dans
        quelques minutes.
      </p>
      <AssistantBusinessPage v-if="isSold" :assistant="shownAssistant" />
      <AssistantDemoPage v-else :assistant="shownAssistant" :is-just-subscribed="isJustSubscribed" />
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { LocationQuery } from 'vue-router'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantPreviewOverrides } from '~/composables/useAssistantPreviewOverrides'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import { computed, onMounted, ref } from 'vue'
import AssistantBusinessPage from '~/components/AssistantBusinessPage.vue'
import AssistantDemoPage from '~/components/AssistantDemoPage.vue'
import { useAssistantPreviewOverrides } from '~/composables/useAssistantPreviewOverrides'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'

const route: ReturnType<typeof useRoute> = useRoute()
const router: ReturnType<typeof useRouter> = useRouter()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()

const { overrides }: { overrides: Ref<AssistantPreviewOverrides> } = useAssistantPreviewOverrides(
  computed((): boolean => route.query._edit === '1'),
)

const {
  data: assistant,
  pending,
  error: loadError,
  refresh,
}: Awaited<ReturnType<typeof useAsyncData<AiAssistantConfig | null>>> = await useAsyncData(
  (): string => `assistant-${routeSlug()}`,
  async (): Promise<AiAssistantConfig | null> => {
    try {
      return await $fetch<AiAssistantConfig>(`${config.public.apiBase}/api/v1/ai-assistants/public/${routeSlug()}`)
    } catch (error: unknown) {
      // Only an unknown or removed receptionist is gone; a passing failure (a deploy, the network) is tried again.
      if (ApiRefusalUtils.status(error) === 404) return null
      throw error
    }
  },
)

/** Back from the checkout: the thanks show once, and the address loses the marker before anyone copies it. */
const isJustSubscribed: Ref<boolean> = ref(route.query.subscribed === '1')

/** The receptionist as shown: the published one, under the unsaved edits of the atelier while it is open. */
const shownAssistant: ComputedRef<AiAssistantConfig | null> = computed((): AiAssistantConfig | null => {
  if (!assistant.value) return null
  return {
    ...assistant.value,
    assistant_name: overrides.value.assistantName ?? assistant.value.assistant_name,
    business_name: overrides.value.businessName ?? assistant.value.business_name,
    accent_color: overrides.value.accentColor ?? assistant.value.accent_color,
  }
})

/** Once sold, the address leads the business's customers to their page: the demo is for the business only. */
const isSold: ComputedRef<boolean> = computed((): boolean => assistant.value?.status === 'delivered')

const palette: ComputedRef<AssistantAccentPalette> = computed((): AssistantAccentPalette =>
  AssistantAccentUtils.palette(shownAssistant.value?.accent_color),
)

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--a-accent': palette.value.accent,
  '--a-accent-strong': palette.value.strong,
  '--a-accent-text': palette.value.text,
}))

const businessName: ComputedRef<string> = computed((): string =>
  BusinessNameUtils.short(shownAssistant.value?.business_name ?? ''),
)

const pageTitle: ComputedRef<string> = computed((): string => {
  if (!businessName.value) return 'Réceptionniste IA'
  return isSold.value ? `${businessName.value} : demande de devis et rendez-vous` : businessName.value
})

const businessDescription: ComputedRef<string | undefined> = computed((): string | undefined => {
  if (!isSold.value || !assistant.value) return undefined
  const lead: string = `${businessName.value}${BusinessNameUtils.tradeAndCityAfterName(assistant.value.trade_label ?? null, assistant.value.city ?? null)}`
  return `${lead}. Posez votre question, envoyez une photo ou demandez un rendez-vous, même en dehors des horaires.`
})

/**
 * The assistant's slug, as the address names it.
 * @returns The slug.
 */
function routeSlug(): string {
  return String(route.params.slug ?? '')
}

onMounted(async (): Promise<void> => {
  // Rendered on the server while the API was briefly down: one more try from the visitor's browser.
  if (loadError.value) await refresh()
  if (!isJustSubscribed.value) return
  const query: LocationQuery = { ...route.query }
  delete query.subscribed
  await router.replace({ query })
})

useSeoMeta({
  title: (): string => pageTitle.value,
  ogTitle: (): string => pageTitle.value,
  description: (): string | undefined => businessDescription.value,
  ogDescription: (): string | undefined => businessDescription.value,
  robots: (): string => (isSold.value ? 'index, follow' : 'noindex'),
  themeColor: (): string | undefined => (isSold.value ? palette.value.accent : undefined),
})
</script>

<style scoped>
.ia-page {
  --ia-paper: #f7f3ec;
  --ia-card: #fffdf9;
  --ia-ink: #17130d;
  --ia-ink-dim: #6d665b;
  --ia-line: rgba(23, 19, 13, 0.14);
  --ia-line-soft: rgba(23, 19, 13, 0.07);
  --ia-font-display: 'Fraunces', Georgia, serif;
  --ia-font-body: 'Inter', system-ui, sans-serif;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--ia-paper);
  color: var(--ia-ink);
  font-family: var(--ia-font-body);
  font-size: 15px;
  line-height: 1.5;
}
.ia-page__notice {
  margin: 0;
  padding: 12px 24px;
  border-bottom: 1px solid var(--ia-line);
  background: var(--ia-card);
  font-size: 14px;
  line-height: 1.5;
  text-align: center;
  color: var(--ia-ink);
}
.ia-page__message {
  margin: auto;
  color: var(--ia-ink-dim);
  text-align: center;
}
.ia-page__message--error {
  color: #9f3a2f;
}
.ia-page__retry {
  margin-top: 10px;
  padding: 10px 18px;
  border: 1px solid var(--ia-line);
  border-radius: 999px;
  background: var(--ia-card);
  font: inherit;
  font-weight: 600;
  color: var(--ia-ink);
  cursor: pointer;
}
</style>
