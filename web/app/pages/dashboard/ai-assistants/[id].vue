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
            <span v-if="assistant.needs_follow_up" class="app-badge app-badge--strong">
              <UIcon name="i-lucide-phone-call" class="h-3 w-3" />
              À relancer
            </span>
          </p>
          <p v-if="assistant.needs_follow_up" class="text-sm text-[var(--app-ink)]">
            Les deux relances automatiques sont parties. Il manque encore :
            {{ missingStartStepsLabel(assistant.missing_start_steps) }}.
          </p>
        </div>
      </header>

      <div class="grid items-start gap-6 @4xl:grid-cols-[360px_1fr]">
        <aside class="card space-y-5 p-5 @4xl:sticky @4xl:top-6 @4xl:max-h-[calc(100vh-3rem)] @4xl:overflow-y-auto">
          <UiTabs v-model="activeTab" :tabs="asideTabs" />

          <template v-if="activeTab === 'resume'">
            <AssistantSummaryCard :assistant="assistant" />
            <AssistantActionsCard
              :status="assistant.status"
              :is-regenerating="isRegenerating"
              :is-sending-client-link="isSendingClientLink"
              :is-revoking-client-links="isRevokingClientLinks"
              :client-space-link-to-copy="clientSpaceLinkToCopy"
              :is-marking-sold="isMarkingSold"
              :is-deleting="isDeleting"
              @regenerate="regenerateAssistant"
              @send-client-space="clientSpaceConfirmModal?.open()"
              @revoke-client-links="revokeLinksConfirmModal?.open()"
              @mark-sold="soldConfirmModal?.open()"
              @remove="deleteConfirmModal?.open()"
            />
            <AssistantVideoCard
              :assistant="assistant"
              :is-busy="isVideoBusy"
              :is-removing-video="isRemovingVideo"
              :is-taking-longer-than-expected="isVideoTakingLongerThanExpected"
              @generate="generateVideo"
              @remove-video="videoDeleteConfirmModal?.open()"
              @refresh-video="refreshVideoStatusNow"
            />
            <AssistantSubscriptionCard :assistant="assistant" />
          </template>

          <AssistantSettingsForm v-else :assistant="assistant" @saved="onAssistantSaved" />
        </aside>

        <section v-if="activeTab === 'config'" class="space-y-6">
          <AssistantDemoPreviewCard
            :demo-url="demoUrl"
            :reload-key="previewReloadKey"
            height-class="h-[calc(100vh-11rem)] min-h-[640px]"
          />
        </section>

        <section v-else class="space-y-6">
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

          <AssistantFaqCard :assistant-id="assistant.id" :assistant-name="assistant.assistant_name" />

          <AssistantInstallGuideCard :embed-snippet="assistant.embed_snippet" />

          <AssistantDemoPreviewCard :demo-url="demoUrl" :reload-key="previewReloadKey" />
        </section>
      </div>
    </template>

    <UiConfirmModal
      ref="deleteConfirmModal"
      title="Supprimer l'assistant"
      :message="deleteConfirmMessage"
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
    <UiConfirmModal
      ref="revokeLinksConfirmModal"
      title="Couper les anciens liens"
      message="Tous les liens envoyés jusqu'ici, alertes SMS comprises, ne marcheront plus."
      confirm-text="Couper les liens"
      cancel-text="Annuler"
      @confirm="revokeClientLinks"
    />
    <UiConfirmModal
      ref="newClientLinkConfirmModal"
      title="Anciens liens coupés"
      :message="newClientLinkConfirmMessage"
      confirm-text="Envoyer un nouveau lien à l'entreprise"
      cancel-text="Plus tard"
      confirm-button-variant="primary"
      @confirm="sendClientSpace"
    />
    <UiConfirmModal
      ref="videoDeleteConfirmModal"
      title="Supprimer la vidéo"
      message="Supprimer la vidéo de prospection de cette réceptionniste ? Le lien envoyé dans les emails et SMS ne fonctionnera plus."
      confirm-text="Supprimer"
      cancel-text="Annuler"
      @confirm="removeVideo"
    />
    <UiConfirmModal
      ref="soldConfirmModal"
      title="Marquer comme vendu"
      :message="soldConfirmMessage"
      confirm-text="Marquer vendu"
      cancel-text="Annuler"
      confirm-button-variant="primary"
      @confirm="markSold"
    />

    <UiVideoGenerationModal
      :open="videoProgress.isOpen.value"
      title="Génération de la vidéo"
      :steps="videoProgress.steps.value"
      :log-lines="videoProgress.logLines.value"
      :elapsed-seconds="videoProgress.elapsedSeconds.value"
      :error-message="videoProgress.errorMessage.value"
      :is-running="videoProgress.isRunning.value"
      @close="videoProgress.close()"
    />
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { UseVideoGenerationProgressReturn } from '~/composables/useVideoGenerationProgress'
import type {
  AiAssistantClientLink,
  AiAssistantRequestItem,
  AiAssistantRequestsResponse,
  AiAssistantSummary,
} from '~/types/AiAssistant'
import type { AiAssistantDetailStat } from '~/types/AiAssistantDetailPage'
import type { AssistantVideoBuildResult } from '~/types/AssistantSidecar'
import type { UseOpenExternalUrlReturn, UseToastReturn, UseVideoGenerationFollowUpReturn } from '~/types/Composables'
import type { AssistantMutationNotice, AssistantRequestMutationNotice } from '~/types/DrawerStack'
import type { UiConfirmModalHandle } from '~/types/UiConfirmModal'
import type { UiTab } from '~/types/UiTabs'
import { computed, onMounted, ref, watch } from 'vue'
import AssistantActionsCard from '~/components/ai-assistants/AssistantActionsCard.vue'
import AssistantDemoPreviewCard from '~/components/ai-assistants/AssistantDemoPreviewCard.vue'
import AssistantFaqCard from '~/components/ai-assistants/AssistantFaqCard.vue'
import AssistantInstallGuideCard from '~/components/ai-assistants/AssistantInstallGuideCard.vue'
import AssistantPortrait from '~/components/ai-assistants/AssistantPortrait.vue'
import AssistantRecentRequests from '~/components/ai-assistants/AssistantRecentRequests.vue'
import AssistantSettingsForm from '~/components/ai-assistants/AssistantSettingsForm.vue'
import AssistantSubscriptionCard from '~/components/ai-assistants/AssistantSubscriptionCard.vue'
import AssistantSummaryCard from '~/components/ai-assistants/AssistantSummaryCard.vue'
import AssistantVideoCard from '~/components/ai-assistants/AssistantVideoCard.vue'
import { useToast } from '~/composables/useToast'
import { useVideoGenerationFollowUp } from '~/composables/useVideoGenerationFollowUp'
import { useVideoGenerationProgress } from '~/composables/useVideoGenerationProgress'
import { RECEPTIONIST_VIDEO_BUILD_PHASES } from '~/constants/videoBuildPhases'
import { AiAssistantService } from '~/services/aiAssistantService'
import { AssistantSidecarService } from '~/services/assistantSidecarService'
import { useDrawerStackStore } from '~/stores/drawerStack'
import { assistantStatusLabel, demoUrlWithInternal, missingStartStepsLabel } from '~/utils/aiAssistantLabels'
import { assistantPortraitUrl } from '~/utils/assistantPortrait'
import { ClipboardCopy } from '~/utils/clipboardCopy'

definePageMeta({ layout: 'dashboard', middleware: ['auth', 'ai-assistant-module'] })

const route: ReturnType<typeof useRoute> = useRoute()
const router: ReturnType<typeof useRouter> = useRouter()
const toast: UseToastReturn = useToast()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()
const { openExternalUrl }: UseOpenExternalUrlReturn = useOpenExternalUrl()
const videoProgress: UseVideoGenerationProgressReturn = useVideoGenerationProgress(RECEPTIONIST_VIDEO_BUILD_PHASES)
const {
  isTakingLongerThanExpected: isVideoTakingLongerThanExpected,
  start: followVideoGeneration,
  refreshNow: refreshVideoStatusNow,
}: UseVideoGenerationFollowUpReturn = useVideoGenerationFollowUp(
  refreshAssistant,
  (): boolean => isVideoGenerating.value,
)

/** How many of the assistant's requests the detail page lists. */
const RECENT_REQUESTS_LIMIT: number = 6

/** Start of the API refusal to delete an assistant still paid for, shown as it is. */
const SUBSCRIPTION_STILL_PAID_REFUSAL: string = "Résiliez d'abord l'abonnement"

/** The aside's tabs: the summary and actions, or the configuration with the demo preview beside it. */
const asideTabs: UiTab[] = [
  { key: 'resume', label: 'Résumé', icon: 'i-lucide-clipboard-list' },
  { key: 'config', label: 'Configuration', icon: 'i-lucide-sliders-horizontal' },
]

const assistant: Ref<AiAssistantSummary | null> = ref(null)
const activeTab: Ref<string> = ref('resume')
/** Bumped after each save so the demo preview shows the new persona, colour or name at once. */
const previewReloadKey: Ref<number> = ref(0)
const requests: Ref<AiAssistantRequestItem[]> = ref([])
const pending: Ref<boolean> = ref(true)
const loadError: Ref<string | null> = ref(null)
const isRegenerating: Ref<boolean> = ref(false)
const isDeleting: Ref<boolean> = ref(false)
const isSendingClientLink: Ref<boolean> = ref(false)
const isRevokingClientLinks: Ref<boolean> = ref(false)
/** The client-space link the browser refused to copy, shown in a field with its own copy button. */
const clientSpaceLinkToCopy: Ref<string | null> = ref(null)
const isMarkingSold: Ref<boolean> = ref(false)
const isVideoBusy: Ref<boolean> = ref(false)
const isRemovingVideo: Ref<boolean> = ref(false)
const deleteConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const clientSpaceConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const revokeLinksConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const newClientLinkConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const soldConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const videoDeleteConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)

const assistantId: ComputedRef<number> = computed((): number => Number(route.params.id))

const pageTitle: ComputedRef<string> = computed(
  (): string => `${assistant.value?.business_name ?? 'Réceptionniste IA'} — DevLeadHunter`,
)

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

/** « à patron@toitures-morel.fr », or the business's known address when the assistant has none. */
const businessRecipientLabel: ComputedRef<string> = computed((): string =>
  assistant.value?.email ? `à ${assistant.value.email}` : "à l'adresse connue du commerce",
)

const clientSpaceConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Envoyer au commerçant ${businessRecipientLabel.value} le lien de son espace (demandes, rapport, réglages, abonnement) ? Le lien est aussi copié.`,
)

const deleteConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Supprimer l'assistant de « ${assistant.value?.business_name ?? ''} » ? Sa démo et son widget s'arrêtent. Sont effacés : ses documents, ses conversations, les demandes et les photos des visiteurs, les rendez-vous, les rapports, l'agenda connecté et la vidéo. Les ventes et les abonnements passés restent.`,
)

const newClientLinkConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Les liens déjà envoyés ne s'ouvrent plus. Envoyer ${businessRecipientLabel.value} un nouveau lien de son espace ? Le lien est aussi copié.`,
)

const soldConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Marquer l'assistant de « ${assistant.value?.business_name ?? ''} » comme vendu hors Stripe (virement, votre propre entreprise) ? Il n'expire plus, chaque demande alerte le commerçant par e-mail et SMS, et l'entreprise reçoit son e-mail de bienvenue avec l'espace client.`,
)

useSeoMeta({ title: pageTitle })

/** Open the journal of what the visitors asked. */
function openConversations(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-conversations', assistant: assistant.value })
}

/** Open what the assistant reads: website, Google listing, documents. */
function openSources(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-sources', assistant: assistant.value })
}

/**
 * The configuration was saved: show the assistant as the API returned it, everywhere, preview included.
 * @param updated - The assistant as the API returned it.
 */
function onAssistantSaved(updated: AiAssistantSummary): void {
  assistant.value = updated
  drawerStack.notifyAssistantUpdated(updated)
  previewReloadKey.value += 1
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
 * Mark the assistant sold outside Stripe: served for good, its owner alerted, the business welcomed.
 * @returns A promise resolved once marked (or refused).
 */
async function markSold(): Promise<void> {
  if (!assistant.value || isMarkingSold.value) return
  isMarkingSold.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.markSold(assistant.value.id)
    assistant.value = updated
    drawerStack.notifyAssistantUpdated(updated)
    toast.success("Assistant marqué vendu : il alerte le commerçant et l'e-mail de bienvenue est parti.")
  } catch {
    toast.error('Impossible de marquer cet assistant vendu pour le moment.')
  } finally {
    isMarkingSold.value = false
  }
}

/**
 * Email the business its client-space link and copy it, from the confirming click so Safari allows the copy.
 * @returns A promise resolved once sent (or refused).
 */
async function sendClientSpace(): Promise<void> {
  if (!assistant.value) return
  isSendingClientLink.value = true
  clientSpaceLinkToCopy.value = null
  const linkRequest: Promise<AiAssistantClientLink> = AiAssistantService.issueClientLink(assistant.value.id, true)
  const copyAttempt: Promise<boolean> = ClipboardCopy.copyWhenReady(
    linkRequest.then((link: AiAssistantClientLink): string => link.url),
  )
  try {
    const link: AiAssistantClientLink = await linkRequest
    const isCopied: boolean = await copyAttempt
    const copyNote: string = isCopied ? ' Lien copié.' : ''
    if (!isCopied) clientSpaceLinkToCopy.value = link.url
    if (link.sent_to) {
      toast.success(`Espace client envoyé à ${link.sent_to}.${copyNote}`)
    } else {
      toast.error(`Email non envoyé : ${(link.send_error ?? 'raison inconnue').replace(/\.+$/, '')}.${copyNote}`)
    }
  } catch {
    toast.error("Lien de l'espace client indisponible pour l'instant.")
  } finally {
    isSendingClientLink.value = false
  }
}

/**
 * Stop every client-space link sent so far, then offer to send the business a new one.
 * @returns A promise resolved once the links are cut (or the cut refused).
 */
async function revokeClientLinks(): Promise<void> {
  if (!assistant.value || isRevokingClientLinks.value) return
  isRevokingClientLinks.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.revokeClientLinks(assistant.value.id)
    assistant.value = updated
    clientSpaceLinkToCopy.value = null
    drawerStack.notifyAssistantUpdated(updated)
    newClientLinkConfirmModal.value?.open()
  } catch {
    toast.error('Impossible de couper les liens pour le moment.')
  } finally {
    isRevokingClientLinks.value = false
  }
}

/**
 * Delete the assistant (its files and its visitors' data are erased) and go back to the list.
 * @returns A promise resolved once removed (or refused).
 */
async function removeAssistant(): Promise<void> {
  if (!assistant.value || isDeleting.value) return
  isDeleting.value = true
  try {
    await AiAssistantService.remove(assistant.value.id)
    drawerStack.notifyAssistantDeleted(assistant.value.id)
    toast.success('Assistant supprimé, ses fichiers et les données de ses visiteurs sont effacés.')
    await router.push('/dashboard/ai-assistants')
  } catch (error: unknown) {
    const detail: string = error instanceof Error ? error.message : ''
    toast.error(detail.startsWith(SUBSCRIPTION_STILL_PAID_REFUSAL) ? detail : "Suppression impossible pour l'instant.")
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
  videoProgress.start(assistant.value.slug, 'Publication de la vidéo')
  try {
    const build: AssistantVideoBuildResult = await AssistantSidecarService.buildFullVideo(assistant.value.id)
    if (build.status === 'done' && build.assistant) {
      videoProgress.finish()
      assistant.value = build.assistant
      videoProgress.close()
      toast.success('Vidéo générée sur votre ordinateur.')
      return
    }
    if (build.status === 'unavailable') {
      videoProgress.close()
    } else {
      // The window stays open with the error and its log, and says the server takes over.
      videoProgress.fail(build.message ?? 'Échec de la génération locale.')
      videoProgress.note('Bascule sur le serveur…')
    }
    assistant.value = await AiAssistantService.generateVideo(assistant.value.id)
    followVideoGeneration()
    videoProgress.note('Montage lancé sur le serveur, suivi sur la carte « Vidéo de prospection ».')
    toast.success('Génération de la vidéo lancée.')
  } catch (error: unknown) {
    const message: string = error instanceof Error ? error.message : 'Échec du lancement de la génération.'
    videoProgress.fail(message)
    toast.error(message)
  } finally {
    isVideoBusy.value = false
  }
}

/**
 * Delete the prospection video: its files, its link and its state.
 * @returns A promise resolved once deleted (or refused).
 */
async function removeVideo(): Promise<void> {
  if (!assistant.value || isRemovingVideo.value) return
  isRemovingVideo.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.clearVideo(assistant.value.id)
    assistant.value = updated
    drawerStack.notifyAssistantUpdated(updated)
    toast.success('Vidéo supprimée.')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Suppression de la vidéo impossible.')
  } finally {
    isRemovingVideo.value = false
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
    // A missed check is not worth a toast: the next one, or the refresh button, tries again.
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
      (listedRequest: AiAssistantRequestItem): AiAssistantRequestItem =>
        listedRequest.id === notice.request.id ? notice.request : listedRequest,
    )
  },
)

onMounted(async (): Promise<void> => {
  await loadData()
  if (isVideoGenerating.value) followVideoGeneration()
})
</script>
