<template>
  <article
    class="card group relative overflow-hidden transition-all duration-300 hover:border-[var(--app-ink-soft)] hover:shadow-lg hover:shadow-black/20"
  >
    <NuxtLink
      :to="`/dashboard/ai-assistants/${props.assistant.id}`"
      class="absolute inset-0 z-10"
      :aria-label="`Voir le détail de l'assistant de ${props.assistant.business_name}`"
    />

    <div
      ref="previewContainer"
      class="relative h-40 overflow-hidden border-b border-[var(--app-line)] bg-[var(--app-surface-2)] transition-transform duration-500 group-hover:scale-[1.02]"
    >
      <div
        v-if="!isPreviewLoaded"
        :class="['absolute inset-0 flex items-center justify-center', shouldRenderPreview ? 'animate-pulse' : '']"
      >
        <UIcon name="i-lucide-bot" class="h-6 w-6 text-[var(--app-faint)]" />
      </div>
      <iframe
        v-if="shouldRenderPreview"
        :src="previewUrl"
        :class="[
          'pointer-events-none absolute top-0 left-0 h-[400%] w-[400%] origin-top-left scale-[0.25] border-0 bg-white transition-opacity duration-500',
          isPreviewLoaded ? 'opacity-100' : 'opacity-0',
        ]"
        loading="lazy"
        tabindex="-1"
        aria-hidden="true"
        title="Aperçu de la page de démo"
        sandbox="allow-scripts allow-same-origin"
        @load="onPreviewLoad"
      ></iframe>
      <span
        class="absolute top-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-0.5 text-[10px] font-bold tracking-wide text-white uppercase backdrop-blur-sm"
      >
        <span :class="['h-1.5 w-1.5 rounded-full', statusDotClass]"></span>
        {{ statusLabel }}
      </span>
      <span
        v-if="props.assistant.churn_risk"
        class="absolute top-3 right-3 inline-flex items-center gap-1 rounded-full bg-black/60 px-2.5 py-0.5 text-[10px] font-bold tracking-wide text-white uppercase backdrop-blur-sm"
        title="Abonné depuis plus de 30 jours, aucune conversation ni demande sur les 30 derniers jours"
      >
        <UIcon name="i-lucide-triangle-alert" class="h-3 w-3" />
        Risque
      </span>
    </div>

    <div class="space-y-4 p-5">
      <div class="min-w-0">
        <h2 class="truncate text-lg font-semibold text-[var(--app-ink)]">{{ props.assistant.business_name }}</h2>
        <p class="text-xs text-[var(--app-ink-soft)]">{{ props.assistant.assistant_name }} · {{ languagesLabel }}</p>
      </div>

      <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--app-ink-soft)]">
        <span class="flex items-center gap-1.5">
          <UIcon name="i-lucide-clock" class="h-3.5 w-3.5" />
          {{ lifetimeLabel }}
        </span>
        <span class="flex items-center gap-1.5 tabular-nums" :title="countsTitle">
          <UIcon name="i-lucide-inbox" class="h-3.5 w-3.5" />
          {{ props.assistant.requests_30d }} demande{{ props.assistant.requests_30d > 1 ? 's' : '' }} / 30 j
        </span>
        <span class="flex items-center gap-1.5 tabular-nums">
          <UIcon name="i-lucide-messages-square" class="h-3.5 w-3.5" />
          {{ props.assistant.conversations_30d }} conv. / 30 j
        </span>
      </div>

      <div class="relative z-20 flex flex-wrap gap-2">
        <button type="button" class="btn-primary h-9 px-4 text-xs" @click="emit('open', demoUrl)">
          Ouvrir la démo
        </button>
        <NuxtLink :to="`/dashboard/ai-assistants/${props.assistant.id}`" class="btn-secondary h-9 px-4 text-xs">
          Détails
        </NuxtLink>
        <button type="button" class="btn-secondary h-9 px-4 text-xs" @click="copyDemoUrl">
          {{ copied ? 'Copié !' : 'Copier le lien' }}
        </button>
      </div>
    </div>
  </article>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AiAssistantSummary } from '~/types/AiAssistant'
import type { AiAssistantCardEmits, AiAssistantCardProps } from '~/types/AiAssistantCard'
import type { UseLazyPreviewReturn } from '~/types/Composables'
import { useLazyPreview } from '~/composables/useLazyPreview'
import { assistantLifetimeLabel, assistantStatusLabel, demoUrlWithInternal } from '~/utils/aiAssistantLabels'

/** Assistant summary card: live scaled preview of its demo page, stretched-link navigation, open and copy. */
const props: AiAssistantCardProps = defineProps({
  assistant: {
    type: Object as PropType<AiAssistantSummary>,
    required: true,
  },
})

const emit: EmitFn<AiAssistantCardEmits> = defineEmits<AiAssistantCardEmits>()

const copied: Ref<boolean> = ref(false)
const isPreviewLoaded: Ref<boolean> = ref(false)
/** Preview container observed to mount the iframe only once the card is on screen. */
const previewContainer: Ref<HTMLElement | null> = ref(null)

/** The demo page with the internal marker, so the preview never counts as a prospect visit. */
const demoUrl: ComputedRef<string> = computed((): string => demoUrlWithInternal(props.assistant.demo_url))

/** The preview shows the demo page itself, scaled down. */
const previewUrl: ComputedRef<string> = computed((): string => demoUrl.value)

const { shouldRenderPreview, markPreviewLoaded }: UseLazyPreviewReturn = useLazyPreview(
  previewContainer,
  (): boolean => true,
)

const statusLabel: ComputedRef<string> = computed((): string => assistantStatusLabel(props.assistant.status))

const statusDotClass: ComputedRef<string> = computed((): string => {
  if (props.assistant.status === 'active' || props.assistant.status === 'delivered') return 'bg-[var(--app-green)]'
  return 'bg-[var(--app-red)]'
})

/** « FR · EN » */
const languagesLabel: ComputedRef<string> = computed((): string =>
  props.assistant.languages.map((code: string): string => code.toUpperCase()).join(' · '),
)

const lifetimeLabel: ComputedRef<string> = computed((): string => assistantLifetimeLabel(props.assistant))

const countsTitle: ComputedRef<string> = computed(
  (): string =>
    `${props.assistant.requests_7d} demande(s) sur 7 jours, ${props.assistant.requests_30d} sur 30 jours (tests exclus)`,
)

/** The iframe has loaded: show it and free a loading slot. */
function onPreviewLoad(): void {
  isPreviewLoaded.value = true
  markPreviewLoaded()
}

/** Copy the demo URL and show a short confirmation state. */
function copyDemoUrl(): void {
  emit('copy', props.assistant.demo_url)
  copied.value = true
  setTimeout((): void => {
    copied.value = false
  }, 2000)
}
</script>
