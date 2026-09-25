<template>
  <div class="space-y-8">
    <div class="flex flex-col gap-4 @2xl:flex-row @2xl:items-center @2xl:justify-between">
      <NuxtLink to="/dashboard/ai-assistants" class="btn-secondary inline-flex w-fit items-center gap-2">
        <UIcon name="i-lucide-arrow-left" class="h-4 w-4" />
        Retour aux réceptionnistes
      </NuxtLink>
      <div v-if="assistant" class="flex flex-wrap items-center gap-2">
        <button type="button" class="btn-secondary inline-flex items-center gap-2" @click="openConversations">
          <UIcon name="i-lucide-messages-square" class="h-4 w-4" />
          Conversations
        </button>
        <button type="button" class="btn-secondary inline-flex items-center gap-2" @click="openSources">
          <UIcon name="i-lucide-library" class="h-4 w-4" />
          Sources
        </button>
        <button type="button" class="btn-secondary inline-flex items-center gap-2" @click="openSettings">
          <UIcon name="i-lucide-pencil" class="h-4 w-4" />
          Personnaliser
        </button>
        <button type="button" class="btn-primary inline-flex items-center gap-2" @click="openExternalUrl(demoUrl)">
          <UIcon name="i-lucide-external-link" class="h-4 w-4" />
          Ouvrir la démo
        </button>
      </div>
    </div>

    <UiLoader v-if="pending" label="Chargement de l'assistant…" />

    <div
      v-else-if="loadError"
      class="card border-[var(--app-red)]/30 bg-[var(--app-red-soft)] p-6 text-sm text-[var(--app-red)]"
    >
      {{ loadError }}
    </div>

    <template v-else-if="assistant">
      <header class="flex items-start gap-4">
        <AssistantPortrait
          :url="portraitUrl"
          :name="assistant.assistant_name"
          :accent-color="assistant.accent_color"
          size-class="h-14 w-14 text-lg"
        />
        <div class="min-w-0 space-y-2">
          <p class="text-xs font-semibold tracking-wider text-[var(--app-ink-soft)] uppercase">Réceptionniste IA</p>
          <h1 class="app-page-title">{{ assistant.business_name }}</h1>
          <p class="flex flex-wrap items-center gap-2 text-sm text-[var(--app-ink-soft)]">
            <span>{{ assistant.assistant_name }} · {{ assistant.slug }}</span>
            <span class="app-badge" :class="statusBadgeClass">{{ statusLabel }}</span>
            <span
              v-if="assistant.churn_risk"
              class="app-badge app-badge--strong"
              title="Abonné depuis plus de 30 jours, aucune conversation ni demande sur les 30 derniers jours : vérifiez que la bulle apparaît sur son site"
            >
              <UIcon name="i-lucide-triangle-alert" class="h-3 w-3" />
              Risque de désabonnement
            </span>
          </p>
        </div>
      </header>

      <div class="grid items-start gap-6 @4xl:grid-cols-[360px_1fr]">
        <aside class="card space-y-5 p-5 @4xl:sticky @4xl:top-6 @4xl:max-h-[calc(100vh-3rem)] @4xl:overflow-y-auto">
          <AssistantSummaryCard :assistant="assistant" />
          <AssistantActionsCard
            :status="assistant.status"
            :is-regenerating="isRegenerating"
            :is-sending-client-link="isSendingClientLink"
            :is-deleting="isDeleting"
            @regenerate="regenerateAssistant"
            @send-client-space="clientSpaceConfirmModal?.open()"
            @remove="deleteConfirmModal?.open()"
          />
          <AssistantVideoCard :assistant="assistant" :is-busy="isVideoBusy" @generate="generateVideo" />
          <AssistantSubscriptionCard :assistant="assistant" />
        </aside>

        <section class="space-y-6">
          <div class="grid grid-cols-2 gap-4 @5xl:grid-cols-4">
            <UiStatCard
              v-for="stat in stats"
              :key="stat.label"
              :label="stat.label"
              :value="stat.value"
              :icon="stat.icon"
              accent="neutral"
            />
          </div>

          <AssistantRecentRequests
            :assistant-id="assistant.id"
            :assistant-name="assistant.assistant_name"
            :requests="requests"
            @open="openRequest"
          />

          <AssistantInstallGuideCard :embed-snippet="assistant.embed_snippet" />

          <AssistantDemoPreviewCard :demo-url="demoUrl" />
        </section>
      </div>
    </template>

    <UiConfirmModal
      ref="deleteConfirmModal"
      title="Supprimer l'assistant"
      :message="`Supprimer l'assistant de « ${assistant?.business_name ?? ''} » ? Sa démo, son widget et ses demandes ne seront plus servis.`"
      confirm-text="Supprimer"
      cancel-text="Annuler"
      @confirm="removeAssistant"
    />
    <UiConfirmModal
      ref="clientSpaceConfirmModal"
      title="Envoyer l'espace client"
      :message="clientSpaceConfirmMessage"
      confirm-text="Envoyer"
      cancel-text="Annuler"
      confirm-button-variant="primary"
      @confirm="sendClientSpace"
    />
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { UseOpenExternalUrlReturn, UseToastReturn, UseCopyToClipboardReturn } from '~/types/Composables'
import type {
  AiAssistantClientLink,
  AiAssistantRequestItem,
  AiAssistantRequestsResponse,
  AiAssistantSummary,
} from '~/types/AiAssistant'
import type { AssistantMutationNotice, AssistantRequestMutationNotice } from '~/types/DrawerStack'
import type { AiAssistantDetailStat } from '~/types/AiAssistantDetailPage'
import AssistantActionsCard from '~/components/ai-assistants/AssistantActionsCard.vue'
import AssistantDemoPreviewCard from '~/components/ai-assistants/AssistantDemoPreviewCard.vue'
import AssistantInstallGuideCard from '~/components/ai-assistants/AssistantInstallGuideCard.vue'
import AssistantPortrait from '~/components/ai-assistants/AssistantPortrait.vue'
import AssistantRecentRequests from '~/components/ai-assistants/AssistantRecentRequests.vue'
import AssistantSubscriptionCard from '~/components/ai-assistants/AssistantSubscriptionCard.vue'
import AssistantSummaryCard from '~/components/ai-assistants/AssistantSummaryCard.vue'
import AssistantVideoCard from '~/components/ai-assistants/AssistantVideoCard.vue'
import { AiAssistantService } from '~/services/aiAssistantService'
import { AssistantSidecarService } from '~/services/assistantSidecarService'
import { useToast } from '~/composables/useToast'
import { useDrawerStackStore } from '~/stores/drawerStack'
import { assistantStatusLabel, demoUrlWithInternal } from '~/utils/aiAssistantLabels'
import { assistantPortraitUrl } from '~/utils/assistantPortrait'

definePageMeta({ layout: 'dashboard', middleware: ['auth', 'ai-assistant-module'] })

const route: ReturnType<typeof useRoute> = useRoute()
const router: ReturnType<typeof useRouter> = useRouter()
const toast: UseToastReturn = useToast()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()
const { copy }: UseCopyToClipboardReturn = useCopyToClipboard()
const { openExternalUrl }: UseOpenExternalUrlReturn = useOpenExternalUrl()

/** How many of the assistant's requests the detail page lists. */
const RECENT_REQUESTS_LIMIT: number = 6

const assistantId: ComputedRef<number> = computed((): number => Number(route.params.id))
const assistant: Ref<AiAssistantSummary | null> = ref(null)
const requests: Ref<AiAssistantRequestItem[]> = ref([])
const pending: Ref<boolean> = ref(true)
const loadError: Ref<string | null> = ref(null)
const isRegenerating: Ref<boolean> = ref(false)
const isDeleting: Ref<boolean> = ref(false)
const isSendingClientLink: Ref<boolean> = ref(false)
const isVideoBusy: Ref<boolean> = ref(false)
const videoPollTimer: Ref<ReturnType<typeof setInterval> | null> = ref(null)
const deleteConfirmModal: Ref<{ open: () => void } | null> = ref(null)
const clientSpaceConfirmModal: Ref<{ open: () => void } | null> = ref(null)

useSeoMeta({
  title: computed((): string => `${assistant.value?.business_name ?? 'Réceptionniste IA'} — DevLeadHunter`),
})

const portraitUrl: ComputedRef<string> = computed((): string =>
  assistant.value
    ? assistantPortraitUrl(assistant.value.demo_url, assistant.value.assistant_name, assistant.value.assistant_gender)
    : '',
)

const demoUrl: ComputedRef<string> = computed((): string =>
  assistant.value ? demoUrlWithInternal(assistant.value.demo_url) : '',
)

const statusLabel: ComputedRef<string> = computed((): string =>
  assistant.value ? assistantStatusLabel(assistant.value.status) : '',
)

const statusBadgeClass: ComputedRef<string> = computed((): string => {
  if (assistant.value?.status === 'active') return 'app-badge--success'
  if (assistant.value?.status === 'delivered') return 'app-badge--strong'
  if (assistant.value?.status === 'failed') return 'app-badge--danger'
  return ''
})

const isVideoGenerating: ComputedRef<boolean> = computed(
  (): boolean => assistant.value?.video_status === 'pending' || assistant.value?.video_status === 'generating',
)

/** The four counters of the assistant, tests excluded. */
const stats: ComputedRef<AiAssistantDetailStat[]> = computed((): AiAssistantDetailStat[] => {
  if (!assistant.value) return []
  const outside: string =
    assistant.value.requests_outside_hours_pct === null ? '—' : `${assistant.value.requests_outside_hours_pct} %`
  return [
    { label: 'Conversations · 7 j', value: assistant.value.conversations_7d, icon: 'i-lucide-messages-square' },
    { label: 'Conversations · 30 j', value: assistant.value.conversations_30d, icon: 'i-lucide-messages-square' },
    { label: 'Demandes · 30 j', value: assistant.value.requests_30d, icon: 'i-lucide-inbox' },
    { label: 'Hors horaires', value: outside, icon: 'i-lucide-moon' },
  ]
})

const clientSpaceConfirmMessage: ComputedRef<string> = computed((): string => {
  const recipient: string = assistant.value?.email ? ` à ${assistant.value.email}` : " à l'adresse connue du commerce"
  return `Envoyer au commerçant${recipient} le lien de son espace (demandes, rapport, réglages, abonnement) ? Le lien est aussi copié.`
})

/** Open the journal of what the visitors asked. */
function openConversations(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-conversations', assistant: assistant.value })
}

/** Open what the assistant reads: website, Google listing, documents. */
function openSources(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-sources', assistant: assistant.value })
}

/** Open the settings drawer: identity, alerts, model. */
function openSettings(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-settings', assistant: assistant.value })
}

/**
 * Open a request in its drawer.
 * @param request - The request.
 */
function openRequest(request: AiAssistantRequestItem): void {
  drawerStack.push({ kind: 'assistant-request', request })
}

/**
 * Rebuild the assistant's knowledge from its prospect's latest data, keeping its branding and link.
 * @returns A promise resolved once regenerated.
 */
async function regenerateAssistant(): Promise<void> {
  if (!assistant.value || isRegenerating.value) return
  isRegenerating.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.regenerate(assistant.value.id)
    assistant.value = updated
    drawerStack.notifyAssistantUpdated(updated)
    toast.success('Assistant régénéré depuis les dernières données du prospect.')
  } catch {
    toast.error('Régénération impossible pour le moment.')
  } finally {
    isRegenerating.value = false
  }
}

/**
 * Email the business its client-space link and copy it.
 * @returns A promise resolved once sent (or refused).
 */
async function sendClientSpace(): Promise<void> {
  if (!assistant.value) return
  isSendingClientLink.value = true
  try {
    const link: AiAssistantClientLink = await AiAssistantService.issueClientLink(assistant.value.id, true)
    await copy(link.url)
    if (link.sent_to) {
      toast.success(`Espace client envoyé à ${link.sent_to}. Lien copié.`)
    } else {
      toast.error(`Email non envoyé : ${(link.send_error ?? 'raison inconnue').replace(/\.+$/, '')}. Lien copié.`)
    }
  } catch {
    toast.error("Lien de l'espace client indisponible pour l'instant.")
  } finally {
    isSendingClientLink.value = false
  }
}

/**
 * Soft-delete the assistant and go back to the list.
 * @returns A promise resolved once removed.
 */
async function removeAssistant(): Promise<void> {
  if (!assistant.value || isDeleting.value) return
  isDeleting.value = true
  try {
    await AiAssistantService.remove(assistant.value.id)
    drawerStack.notifyAssistantDeleted(assistant.value.id)
    toast.success('Assistant supprimé.')
    await router.push('/dashboard/ai-assistants')
  } catch {
    toast.error("Suppression impossible pour l'instant.")
  } finally {
    isDeleting.value = false
  }
}

/**
 * Start (or restart) the prospection video: on the desktop app first, on the server otherwise.
 * @returns A promise resolved once the generation is requested.
 */
async function generateVideo(): Promise<void> {
  if (!assistant.value || isVideoBusy.value) return
  isVideoBusy.value = true
  try {
    const build: Awaited<ReturnType<typeof AssistantSidecarService.buildFullVideo>> =
      await AssistantSidecarService.buildFullVideo(assistant.value.id)
    if (build.status === 'done' && build.assistant) {
      assistant.value = build.assistant
      toast.success('Vidéo générée sur votre ordinateur.')
      return
    }
    if (build.status === 'failed') toast.info('Génération locale indisponible, bascule sur le serveur…')
    assistant.value = await AiAssistantService.generateVideo(assistant.value.id)
    toast.success('Génération de la vidéo lancée.')
    startVideoPolling()
  } catch {
    toast.error("Vidéo impossible : enregistrez d'abord votre clip webcam « assistant » dans les paramètres.")
  } finally {
    isVideoBusy.value = false
  }
}

/** Poll the assistant every few seconds while its video is generating, then stop. */
function startVideoPolling(): void {
  if (videoPollTimer.value !== null) return
  videoPollTimer.value = setInterval((): void => {
    if (!isVideoGenerating.value) {
      stopVideoPolling()
      return
    }
    refreshAssistant()
  }, 5000)
}

/** Stop the video-generation poll. */
function stopVideoPolling(): void {
  if (videoPollTimer.value !== null) {
    clearInterval(videoPollTimer.value)
    videoPollTimer.value = null
  }
}

/**
 * Refresh the assistant alone (video progress), leaving the page as it is.
 * @returns A promise resolved once refreshed.
 */
async function refreshAssistant(): Promise<void> {
  try {
    assistant.value = await AiAssistantService.get(assistantId.value)
  } catch {
    // A missed poll is not worth a toast every five seconds.
  }
}

/**
 * Load the assistant and its latest requests.
 * @returns A promise resolved once loaded.
 */
async function loadData(): Promise<void> {
  pending.value = true
  loadError.value = null
  try {
    const [loaded, requestList]: [AiAssistantSummary, AiAssistantRequestsResponse] = await Promise.all([
      AiAssistantService.get(assistantId.value),
      AiAssistantService.listRequests(undefined, assistantId.value),
    ])
    assistant.value = loaded
    requests.value = requestList.requests.slice(0, RECENT_REQUESTS_LIMIT)
  } catch {
    loadError.value = 'Assistant introuvable ou indisponible pour le moment.'
  } finally {
    pending.value = false
  }
}

watch(
  (): number => drawerStack.assistantMutationCounter,
  (): void => {
    const notice: AssistantMutationNotice | null = drawerStack.lastAssistantMutation
    if (notice?.type === 'updated' && notice.assistant.id === assistantId.value) assistant.value = notice.assistant
  },
)

watch(
  (): number => drawerStack.requestMutationCounter,
  (): void => {
    const notice: AssistantRequestMutationNotice | null = drawerStack.lastRequestMutation
    if (notice?.type !== 'updated') return
    requests.value = requests.value.map(
      (item: AiAssistantRequestItem): AiAssistantRequestItem => (item.id === notice.request.id ? notice.request : item),
    )
  },
)

onMounted(async (): Promise<void> => {
  await loadData()
  if (isVideoGenerating.value) startVideoPolling()
})

onUnmounted((): void => {
  stopVideoPolling()
})
</script>
