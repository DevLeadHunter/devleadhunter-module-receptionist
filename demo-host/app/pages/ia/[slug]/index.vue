<template>
  <div class="ia-page" :style="accentStyle">
    <p v-if="pending" class="ia-page__message">Chargement…</p>
    <p v-else-if="!assistant" class="ia-page__message ia-page__message--error">Cette page n'est plus disponible.</p>
    <template v-else>
      <p v-if="isJustSubscribed" class="ia-page__notice" role="status">
        C'est fait : {{ assistant.assistant_name }} est à vous. Le lien de votre espace arrive par e-mail dans quelques
        minutes.
      </p>
      <AssistantBusinessPage v-if="isSold" :assistant="assistant" />
      <AssistantDemoPage v-else :assistant="assistant" :is-just-subscribed="isJustSubscribed" />
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { LocationQuery } from 'vue-router'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import { computed, onMounted, ref } from 'vue'
import AssistantBusinessPage from '~/components/AssistantBusinessPage.vue'
import AssistantDemoPage from '~/components/AssistantDemoPage.vue'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'

const route: ReturnType<typeof useRoute> = useRoute()
const router: ReturnType<typeof useRouter> = useRouter()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()

const { data: assistant, pending }: Awaited<ReturnType<typeof useAsyncData<AiAssistantConfig | null>>> =
  await useAsyncData(
    (): string => `assistant-${routeSlug()}`,
    async (): Promise<AiAssistantConfig | null> => {
      try {
        return await $fetch<AiAssistantConfig>(`${config.public.apiBase}/api/v1/ai-assistants/public/${routeSlug()}`)
      } catch {
        return null
      }
    },
  )

/** Back from the checkout: the thanks show once, and the address loses the marker before anyone copies it. */
const isJustSubscribed: Ref<boolean> = ref(route.query.subscribed === '1')

/** Once sold, the address leads the business's customers to their page: the demo is for the business only. */
const isSold: ComputedRef<boolean> = computed((): boolean => assistant.value?.status === 'delivered')

const palette: ComputedRef<AssistantAccentPalette> = computed((): AssistantAccentPalette =>
  AssistantAccentUtils.palette(assistant.value?.accent_color),
)

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--a-accent': palette.value.accent,
  '--a-accent-strong': palette.value.strong,
  '--a-accent-text': palette.value.text,
}))

const businessName: ComputedRef<string> = computed((): string =>
  BusinessNameUtils.short(assistant.value?.business_name ?? ''),
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
}
.ia-page__message--error {
  color: #9f3a2f;
}
</style>
