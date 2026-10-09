<template>
  <div :class="props.isFramed ? 'rounded-xl border border-[var(--app-line)] bg-[var(--app-bg)] p-4' : ''">
    <div class="flex items-center justify-between gap-3">
      <h3 v-if="!props.isHeadingHidden" class="text-sm font-semibold text-[var(--app-ink)]">Vidéo de prospection</h3>
      <span v-if="statusLabel" class="app-badge" :class="statusBadgeClass">{{ statusLabel }}</span>
    </div>
    <p class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]">
      Votre webcam, puis la réceptionniste qui répond à l'écran. Le lien et la vignette vont dans les emails via
      {lien_video_assistant} et {vignette_video_assistant}.
    </p>
    <UiDesktopVideoRequest
      v-if="isWaitingForDesktop"
      class="mt-3"
      :is-build-started="props.assistant.is_video_desktop_build_started"
      :is-desktop-app-online="props.isDesktopAppOnline"
      :is-cancelling="props.isCancellingDesktopRequest"
      @cancel="emit('cancel-desktop-request')"
    />
    <p v-else-if="videoFailureMessage" class="mt-3 text-xs text-[var(--app-red)]">
      {{ videoFailureMessage }}
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
        <template v-if="!isWaitingForDesktop">
          <p
            v-if="props.assistant.is_video_made_with_older_clip"
            class="flex items-center gap-1.5 text-xs text-[var(--app-accent-ink)]"
          >
            <UIcon name="i-lucide-history" class="h-3.5 w-3.5 shrink-0" />
            Faite avec un ancien clip
          </p>
          <button
            type="button"
            class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="props.isBusy"
            @click="emit('generate')"
          >
            {{ props.isBusy ? 'Lancement…' : 'Régénérer la vidéo' }}
          </button>
        </template>
        <button
          type="button"
          class="btn-secondary w-full text-xs text-[var(--app-red)] disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="props.isRemovingVideo || props.assistant.is_video_desktop_build_started"
          @click="emit('remove-video')"
        >
          {{ props.isRemovingVideo ? 'Suppression…' : 'Supprimer la vidéo' }}
        </button>
      </div>
    </template>
    <button
      v-if="!isWaitingForDesktop && props.assistant.video_status !== 'ready'"
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
import type { AiAssistantSummary } from '~/types/AiAssistant'
import type { AssistantVideoCardEmits, AssistantVideoCardProps } from '~/types/AssistantVideoCard'
import type { UseCopyToClipboardReturn, UseOpenExternalUrlReturn } from '~/types/Composables'
import { computed } from 'vue'

/** The receptionist's prospection video: where it stands, its links and the buttons to make or remove it. */
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
  isDesktopAppOnline: {
    type: Boolean,
    required: true,
  },
  isCancellingDesktopRequest: {
    type: Boolean,
    default: false,
  },
  isHeadingHidden: {
    type: Boolean,
    default: false,
  },
  isFramed: {
    type: Boolean,
    default: true,
  },
})

const emit: EmitFn<AssistantVideoCardEmits> = defineEmits<AssistantVideoCardEmits>()

const { copy, copied }: UseCopyToClipboardReturn = useCopyToClipboard()
const { openExternalUrl }: UseOpenExternalUrlReturn = useOpenExternalUrl()

const isWaitingForDesktop: ComputedRef<boolean> = computed((): boolean =>
  Boolean(props.assistant.video_desktop_requested_at),
)

const videoFailureMessage: ComputedRef<string | null> = computed((): string | null => {
  if (props.assistant.video_status === 'failed') {
    return props.assistant.video_error || 'La génération a échoué.'
  }
  if (props.assistant.video_status === 'ready' && props.assistant.video_error) {
    return `La nouvelle génération a échoué, la vidéo actuelle reste en ligne. ${props.assistant.video_error}`
  }
  return null
})

const statusLabel: ComputedRef<string> = computed((): string => {
  if (isWaitingForDesktop.value) {
    return props.assistant.is_video_desktop_build_started ? 'En cours' : 'En attente'
  }
  const status: string | null = props.assistant.video_status
  if (status === 'ready') return 'Prête'
  if (status === 'failed') return 'Échec'
  return ''
})

const statusBadgeClass: ComputedRef<string> = computed((): string => {
  if (props.assistant.video_status === 'ready') return 'app-badge--success'
  if (props.assistant.video_status === 'failed') return 'app-badge--danger'
  return ''
})
</script>
