<template>
  <div class="space-y-8">
    <div class="flex flex-col gap-4 @2xl:flex-row @2xl:items-center @2xl:justify-between">
      <NuxtLink to="/dashboard/ai-assistants" class="btn-secondary inline-flex w-fit items-center gap-2">
        <UIcon name="i-lucide-arrow-left" class="h-4 w-4" />
        Retour aux assistants
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
      <header class="space-y-2">
        <p class="text-xs font-semibold tracking-wider text-[var(--app-ink-soft)] uppercase">Assistant IA</p>
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
      </header>

      <div class="grid items-start gap-6 @4xl:grid-cols-[360px_1fr]">
        <aside class="card space-y-5 p-5 @4xl:sticky @4xl:top-6 @4xl:max-h-[calc(100vh-3rem)] @4xl:overflow-y-auto">
          <div>
            <h2 class="text-sm font-semibold tracking-wide text-[var(--app-ink)] uppercase">Résumé</h2>
            <dl class="mt-4 space-y-3 text-xs">
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Statut</dt>
                <dd class="text-right text-[var(--app-ink)]">{{ lifetimeLabel }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Prénom</dt>
                <dd class="text-right text-[var(--app-ink)]">{{ assistant.assistant_name }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Langues</dt>
                <dd class="text-right text-[var(--app-ink)] uppercase">{{ assistant.languages.join(' · ') }}</dd>
              </div>
              <div v-if="assistant.tone" class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Ton</dt>
                <dd class="text-right text-[var(--app-ink)]">{{ assistant.tone }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Couleur</dt>
                <dd class="flex items-center justify-end gap-2 text-[var(--app-ink)]">
                  <span
                    class="inline-block h-3.5 w-3.5 rounded-full border border-[var(--app-line)]"
                    :style="{ background: assistant.accent_color ?? 'transparent' }"
                  />
                  {{ assistant.accent_color ?? 'Neutre' }}
                </dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Email du commerçant</dt>
                <dd class="text-right break-all text-[var(--app-ink)]">{{ assistant.email ?? 'Aucun' }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Mobile d'alerte</dt>
                <dd class="text-right text-[var(--app-ink)]">{{ assistant.alerts.phone ?? 'Aucun' }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Modèle</dt>
                <dd class="text-right text-[var(--app-ink)]">
                  {{ assistant.eu_only ? 'IA hébergée en Europe' : 'Mistral, secours Groq' }}
                </dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-[var(--app-ink-soft)]">Créé le</dt>
                <dd class="text-right text-[var(--app-ink)]">{{ formatNumericDate(assistant.created_at) }}</dd>
              </div>
            </dl>
          </div>

          <div class="border-t border-[var(--app-line)] pt-4">
            <h3 class="text-sm font-semibold text-[var(--app-ink)]">Lien de la démo</h3>
            <div class="mt-2 flex items-center gap-2">
              <input :value="assistant.demo_url" readonly class="input-field h-9 flex-1 truncate text-xs" />
              <button
                type="button"
                class="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded border border-[var(--app-line)] text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]"
                :title="copied ? 'Lien copié !' : 'Copier le lien'"
                @click="copy(assistant.demo_url)"
              >
                <UIcon :name="copied ? 'i-lucide-check' : 'i-lucide-copy'" class="h-4 w-4" />
              </button>
            </div>
          </div>

          <div class="border-t border-[var(--app-line)] pt-4">
            <h3 class="text-sm font-semibold text-[var(--app-ink)]">Script pour le site du client</h3>
            <p class="mt-1 text-xs leading-relaxed text-[var(--app-ink-soft)]">
              Une ligne à coller avant la balise de fin du site : la bulle apparaît en bas à droite.
            </p>
            <code
              class="mt-2 block rounded-md bg-[var(--app-surface-2)] px-2.5 py-2 text-[11px] leading-relaxed break-all text-[var(--app-ink-soft)]"
            >
              {{ assistant.embed_snippet }}
            </code>
            <button type="button" class="btn-secondary mt-2 w-full text-xs" @click="copySnippet">
              <UIcon name="i-lucide-code" class="mr-1.5 h-3.5 w-3.5" />
              Copier le script
            </button>
          </div>

          <div class="space-y-2 border-t border-[var(--app-line)] pt-4">
            <h3 class="text-sm font-semibold text-[var(--app-ink)]">Actions</h3>
            <button
              type="button"
              class="btn-secondary inline-flex w-full items-center justify-center gap-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isRegenerating"
              @click="regenerateAssistant"
            >
              <UIcon
                :name="isRegenerating ? 'i-lucide-loader-circle' : 'i-lucide-refresh-cw'"
                class="h-3.5 w-3.5"
                :class="{ 'animate-spin': isRegenerating }"
              />
              {{ isRegenerating ? 'Régénération…' : 'Régénérer depuis le prospect' }}
            </button>
            <button
              v-if="assistant.status === 'delivered'"
              type="button"
              class="btn-secondary inline-flex w-full items-center justify-center gap-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSendingClientLink"
              @click="clientSpaceConfirmModal?.open()"
            >
              <UIcon
                :name="isSendingClientLink ? 'i-lucide-loader-circle' : 'i-lucide-user-round-key'"
                class="h-3.5 w-3.5"
                :class="{ 'animate-spin': isSendingClientLink }"
              />
              Envoyer l'espace client
            </button>
            <button
              type="button"
              class="btn-secondary w-full text-xs text-[var(--app-red)] disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isDeleting"
              @click="deleteConfirmModal?.open()"
            >
              {{ isDeleting ? 'Suppression…' : "Supprimer l'assistant" }}
            </button>
          </div>

          <div class="rounded-xl border border-[var(--app-line)] bg-[var(--app-bg)] p-4">
            <div class="flex items-center justify-between gap-3">
              <h3 class="text-sm font-semibold text-[var(--app-ink)]">Vidéo de prospection</h3>
              <span v-if="videoStatusLabel" class="app-badge" :class="videoStatusClass">{{ videoStatusLabel }}</span>
            </div>
            <p class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]">
              Votre webcam, puis la réceptionniste qui répond à l'écran. Le lien et la vignette vont dans les emails via
              {lien_video_assistant} et {vignette_video_assistant}.
            </p>
            <div v-if="isVideoGenerating" class="mt-3 flex items-center gap-2 text-xs text-[var(--app-ink-soft)]">
              <UIcon name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
              Génération en cours…
            </div>
            <p v-else-if="assistant.video_status === 'failed'" class="mt-3 text-xs text-[var(--app-red)]">
              {{ assistant.video_error || 'La génération a échoué.' }}
            </p>
            <template v-if="assistant.video_status === 'ready' && assistant.video_page_url">
              <div class="mt-3 space-y-2">
                <button
                  type="button"
                  class="btn-secondary w-full text-xs"
                  @click="openExternalUrl(assistant.video_page_url)"
                >
                  <UIcon name="i-lucide-play" class="mr-1.5 h-3.5 w-3.5" />
                  Voir la vidéo
                </button>
                <button type="button" class="btn-secondary w-full text-xs" @click="copy(assistant.video_page_url)">
                  {{ copied ? 'Lien copié !' : 'Copier le lien vidéo' }}
                </button>
                <button
                  type="button"
                  class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isVideoBusy"
                  @click="generateVideo"
                >
                  {{ isVideoBusy ? 'Lancement…' : 'Régénérer la vidéo' }}
                </button>
              </div>
            </template>
            <button
              v-if="!isVideoGenerating && assistant.video_status !== 'ready'"
              type="button"
              class="btn-primary mt-3 w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isVideoBusy"
              @click="generateVideo"
            >
              <UIcon name="i-lucide-clapperboard" class="mr-1.5 h-3.5 w-3.5" />
              {{ isVideoBusy ? 'Lancement…' : assistant.video_status === 'failed' ? 'Réessayer' : 'Générer la vidéo' }}
            </button>
            <NuxtLink
              to="/dashboard/settings/video"
              class="mt-2 block w-full text-center text-[11px] text-[var(--app-ink-soft)] underline underline-offset-2 transition-colors hover:text-[var(--app-ink)]"
            >
              Configurer mon clip webcam « assistant »
            </NuxtLink>
          </div>

          <div class="rounded-xl border border-[var(--app-line)] bg-[var(--app-bg)] p-4">
            <div class="flex items-center justify-between gap-3">
              <h3 class="text-sm font-semibold text-[var(--app-ink)]">Abonnement</h3>
              <span v-if="assistant.subscription_status === 'active'" class="app-badge app-badge--success">
                Abonné · {{ subscriptionLabel }}
              </span>
            </div>
            <template v-if="assistant.status !== 'delivered'">
              <p class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]">
                Le lien ouvre un paiement Stripe à chaque clic et reste valable : envoyez-le au client quand il dit oui.
              </p>
              <div class="mt-3 space-y-2">
                <button
                  type="button"
                  class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isSubscriptionBusy"
                  @click="copySubscriptionLink('month')"
                >
                  <UIcon name="i-lucide-link" class="mr-1.5 h-3.5 w-3.5" />
                  Copier le lien mensuel
                </button>
                <button
                  type="button"
                  class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isSubscriptionBusy"
                  @click="copySubscriptionLink('year')"
                >
                  <UIcon name="i-lucide-link" class="mr-1.5 h-3.5 w-3.5" />
                  Copier le lien annuel
                </button>
              </div>
            </template>
            <p
              v-else-if="assistant.subscription_status !== 'active'"
              class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]"
            >
              Vendu sans abonnement Stripe enregistré.
            </p>
            <NuxtLink
              v-else
              to="/dashboard/subscriptions"
              class="mt-2 block text-xs text-[var(--app-ink-soft)] underline underline-offset-2 hover:text-[var(--app-ink)]"
            >
              Voir dans Abonnements
            </NuxtLink>
          </div>
        </aside>

        <section class="space-y-6">
          <div class="grid grid-cols-2 gap-4 @4xl:grid-cols-4">
            <div v-for="stat in stats" :key="stat.label" class="card p-4">
              <p class="text-xs font-medium tracking-wide text-[var(--app-ink-soft)] uppercase">{{ stat.label }}</p>
              <p class="mt-1 text-xl font-semibold text-[var(--app-ink)] tabular-nums">{{ stat.value }}</p>
            </div>
          </div>

          <div class="card overflow-hidden p-0">
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--app-line)] px-5 py-4">
              <div>
                <h2 class="font-semibold text-[var(--app-ink)]">Dernières demandes</h2>
                <p class="text-xs text-[var(--app-ink-soft)]">
                  Ce que les visiteurs ont laissé à {{ assistant.assistant_name }}.
                </p>
              </div>
              <NuxtLink
                :to="`/dashboard/ai-assistants/requests?assistant=${assistant.id}`"
                class="btn-secondary h-8 text-xs"
              >
                Toutes les demandes
              </NuxtLink>
            </div>
            <p v-if="requests.length === 0" class="px-5 py-8 text-center text-sm text-[var(--app-ink-soft)]">
              Aucune demande pour l'instant.
            </p>
            <ul v-else class="divide-y divide-[var(--app-line-soft)]">
              <li v-for="request in requests" :key="request.id">
                <button
                  type="button"
                  class="flex w-full cursor-pointer items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-[var(--app-surface-2)]"
                  @click="openRequest(request)"
                >
                  <span class="app-badge shrink-0" :class="request.type === 'urgent' ? 'app-badge--danger' : ''">
                    {{ REQUEST_TYPE_LABELS[request.type] }}
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-sm font-medium text-[var(--app-ink)]">{{ request.name }}</span>
                    <span class="block truncate text-xs text-[var(--app-ink-soft)]">
                      {{ request.need_summary || request.need || 'Demande de rappel, sans détail.' }}
                    </span>
                  </span>
                  <span class="shrink-0 text-xs text-[var(--app-ink-soft)] tabular-nums">
                    {{ formatShortMonthDayTime(request.created_at) }}
                  </span>
                  <span v-if="request.status === 'handled'" class="app-badge app-badge--success shrink-0">Traitée</span>
                  <span v-else-if="request.status === 'dropped'" class="app-badge shrink-0">Sans suite</span>
                  <span v-else class="app-badge app-badge--strong shrink-0">À traiter</span>
                </button>
              </li>
            </ul>
          </div>

          <div class="card overflow-hidden p-0">
            <div class="border-b border-[var(--app-line)] px-5 py-4">
              <h2 class="font-semibold text-[var(--app-ink)]">Aperçu de la page de démo</h2>
              <p class="text-xs text-[var(--app-ink-soft)]">
                Ce que le prospect reçoit : la scène, la conversation, le prix. Vos visites ici ne comptent pas.
              </p>
            </div>
            <iframe
              :src="demoUrl"
              class="h-[720px] w-full border-0 bg-white"
              title="Aperçu de la page de démo"
              loading="lazy"
            />
          </div>
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
import type { UseCopyToClipboardReturn, UseOpenExternalUrlReturn, UseToastReturn } from '~/types/Composables'
import type {
  AiAssistantClientLink,
  AiAssistantRequestItem,
  AiAssistantRequestsResponse,
  AiAssistantSummary,
} from '~/types/AiAssistant'
import type { AssistantMutationNotice, AssistantRequestMutationNotice } from '~/types/DrawerStack'
import type { AiAssistantDetailStat } from '~/types/AiAssistantDetailPage'
import { AiAssistantService } from '~/services/aiAssistantService'
import { AssistantSidecarService } from '~/services/assistantSidecarService'
import { useToast } from '~/composables/useToast'
import { useDrawerStackStore } from '~/stores/drawerStack'
import {
  assistantLifetimeLabel,
  assistantStatusLabel,
  demoUrlWithInternal,
  REQUEST_TYPE_LABELS,
} from '~/utils/aiAssistantLabels'
import { formatNumericDate, formatShortMonthDayTime } from '~/utils/date'

/** One assistant: its summary and links, what it captured, its video and its subscription, and a live preview. */
definePageMeta({ layout: 'dashboard', middleware: 'auth' })

const route: ReturnType<typeof useRoute> = useRoute()
const router: ReturnType<typeof useRouter> = useRouter()
const toast: UseToastReturn = useToast()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()
const { copy, copied }: UseCopyToClipboardReturn = useCopyToClipboard()
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
const isSubscriptionBusy: Ref<boolean> = ref(false)
const videoPollTimer: Ref<ReturnType<typeof setInterval> | null> = ref(null)
const deleteConfirmModal: Ref<{ open: () => void } | null> = ref(null)
const clientSpaceConfirmModal: Ref<{ open: () => void } | null> = ref(null)

useSeoMeta({ title: computed((): string => `${assistant.value?.business_name ?? 'Assistant IA'} — DevLeadHunter`) })

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

const lifetimeLabel: ComputedRef<string> = computed((): string =>
  assistant.value ? assistantLifetimeLabel(assistant.value) : '',
)

/** Human label for the active subscription (« 79 €/mois »). */
const subscriptionLabel: ComputedRef<string> = computed((): string => {
  if (!assistant.value || assistant.value.subscription_amount_cents == null) return ''
  const euros: number = Math.round(assistant.value.subscription_amount_cents / 100)
  return `${euros} €/${assistant.value.subscription_interval === 'year' ? 'an' : 'mois'}`
})

const isVideoGenerating: ComputedRef<boolean> = computed(
  (): boolean => assistant.value?.video_status === 'pending' || assistant.value?.video_status === 'generating',
)

const videoStatusLabel: ComputedRef<string> = computed((): string => {
  const status: string | null = assistant.value?.video_status ?? null
  if (status === 'ready') return 'Prête'
  if (status === 'failed') return 'Échec'
  if (status === 'pending' || status === 'generating') return 'En cours'
  return ''
})

const videoStatusClass: ComputedRef<string> = computed((): string => {
  const status: string | null = assistant.value?.video_status ?? null
  if (status === 'ready') return 'app-badge--success'
  if (status === 'failed') return 'app-badge--danger'
  return ''
})

/** The four counters of the assistant, tests excluded. */
const stats: ComputedRef<AiAssistantDetailStat[]> = computed((): AiAssistantDetailStat[] => {
  if (!assistant.value) return []
  const outside: string =
    assistant.value.requests_outside_hours_pct === null ? '—' : `${assistant.value.requests_outside_hours_pct} %`
  return [
    { label: 'Conversations · 7 j', value: assistant.value.conversations_7d },
    { label: 'Conversations · 30 j', value: assistant.value.conversations_30d },
    { label: 'Demandes · 30 j', value: assistant.value.requests_30d },
    { label: 'Hors horaires', value: outside },
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
 * Copy the embed snippet.
 * @returns A promise resolved once copied.
 */
async function copySnippet(): Promise<void> {
  if (!assistant.value) return
  await copy(assistant.value.embed_snippet)
  toast.success('Script copié : à coller avant </body> du site du client.')
}

/**
 * Copy the permanent subscription link for the client.
 * @param interval - `month` or `year`.
 * @returns A promise resolved once copied.
 */
async function copySubscriptionLink(interval: 'month' | 'year'): Promise<void> {
  if (!assistant.value || isSubscriptionBusy.value) return
  isSubscriptionBusy.value = true
  try {
    const { url }: { url: string } = await AiAssistantService.getSubscriptionLink(assistant.value.id, interval)
    await copy(url)
    toast.success(`Lien d'abonnement ${interval === 'year' ? 'annuel' : 'mensuel'} copié.`)
  } catch {
    toast.error('Lien indisponible pour cet assistant.')
  } finally {
    isSubscriptionBusy.value = false
  }
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
    void refreshAssistant()
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
