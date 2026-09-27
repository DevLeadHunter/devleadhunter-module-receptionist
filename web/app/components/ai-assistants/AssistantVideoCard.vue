<template>
  <div class="rounded-xl border border-[var(--app-line)] bg-[var(--app-bg)] p-4">
    <div class="flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-[var(--app-ink)]">Vidéo de prospection</h3>
      <span v-if="statusLabel" class="app-badge" :class="statusBadgeClass">{{ statusLabel }}</span>
    </div>
    <p class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]">
      Votre webcam, puis la réceptionniste qui répond à l'écran. Le lien et la vignette vont dans les emails via
      {lien_video_assistant} et {vignette_video_assistant}.
    </p>
    <div v-if="isGenerating" class="mt-3 flex items-center gap-2 text-xs text-[var(--app-ink-soft)]">
      <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
      Génération en cours…
    </div>
    <p v-else-if="props.assistant.video_status === 'failed'" class="mt-3 text-xs text-[var(--app-red)]">
      {{ props.assistant.video_error || 'La génération a échoué.' }}
    </p>
    <template v-if="props.assistant.video_status === 'ready' && props.assistant.video_page_url">
      <button
        type="button"
        class="mt-3 block w-full cursor-pointer overflow-hidden rounded-lg border border-[var(--app-line)] transition-opacity hover:opacity-90"
        title="Ouvrir la page vidéo"
        @click="openExternalUrl(props.assistant.video_page_url)"
      >
        <img
          v-if="props.assistant.video_thumbnail_url"
          :src="props.assistant.video_thumbnail_url"
          alt="Vignette de la vidéo de prospection"
          class="w-full"
        />
      </button>
      <div class="mt-2 space-y-2">
        <button type="button" class="btn-secondary w-full text-xs" @click="copy(props.assistant.video_page_url)">
          {{ copied ? 'Lien copié !' : 'Copier le lien vidéo' }}
        </button>
        <button
          type="button"
          class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="props.isBusy"
          @click="emit('generate')"
        >
          {{ props.isBusy ? 'Lancement…' : 'Régénérer la vidéo' }}
        </button>
        <button
          type="button"
          class="btn-secondary w-full text-xs text-[var(--app-red)] disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="props.isRemovingVideo"
          @click="emit('remove-video')"
        >
          {{ props.isRemovingVideo ? 'Suppression…' : 'Supprimer la vidéo' }}
        </button>
      </div>
    </template>
    <button
      v-if="!isGenerating && props.assistant.video_status !== 'ready'"
      type="button"
      class="btn-primary mt-3 w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="props.isBusy"
      @click="emit('generate')"
    >
      <UIcon name="i-lucide-clapperboard" class="mr-1.5 h-3.5 w-3.5" />
      {{ props.isBusy ? 'Lancement…' : props.assistant.video_status === 'failed' ? 'Réessayer' : 'Générer la vidéo' }}
    </button>
    <NuxtLink
      to="/dashboard/settings/video#clip-receptionniste"
      class="mt-2 block w-full text-center text-[11px] text-[var(--app-ink-soft)] underline underline-offset-2 transition-colors hover:text-[var(--app-ink)]"
    >
      Configurer mon clip webcam « réceptionniste »
    </NuxtLink>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantSummary } from '~/types/AiAssistant'
import type { AssistantVideoCardEmits, AssistantVideoCardProps } from '~/types/AssistantVideoCard'
import type { UseCopyToClipboardReturn, UseOpenExternalUrlReturn } from '~/types/Composables'

const props: AssistantVideoCardProps = defineProps({
  assistant: {
    type: Object as PropType<AiAssistantSummary>,
    required: true,
  },
  isBusy: {
    type: Boolean,
    default: false,
  },
  isRemovingVideo: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<AssistantVideoCardEmits> = defineEmits<AssistantVideoCardEmits>()

const { copy, copied }: UseCopyToClipboardReturn = useCopyToClipboard()
const { openExternalUrl }: UseOpenExternalUrlReturn = useOpenExternalUrl()

const isGenerating: ComputedRef<boolean> = computed(
  (): boolean => props.assistant.video_status === 'pending' || props.assistant.video_status === 'generating',
)

const statusLabel: ComputedRef<string> = computed((): string => {
  const status: string | null = props.assistant.video_status
  if (status === 'ready') return 'Prête'
  if (status === 'failed') return 'Échec'
  if (status === 'pending' || status === 'generating') return 'En cours'
  return ''
})

const statusBadgeClass: ComputedRef<string> = computed((): string => {
  if (props.assistant.video_status === 'ready') return 'app-badge--success'
  if (props.assistant.video_status === 'failed') return 'app-badge--danger'
  return ''
})
</script>
