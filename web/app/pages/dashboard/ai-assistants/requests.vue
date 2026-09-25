<template>
  <div class="flex min-h-full flex-col gap-6">
    <div>
      <p class="text-xs font-semibold tracking-wider text-[var(--app-ink-soft)] uppercase">Module IA</p>
      <h1 class="app-page-title mt-1">Demandes</h1>
      <p class="mt-2 max-w-xl text-sm text-[var(--app-ink-soft)]">
        Chaque visiteur qui laisse ses coordonnées à une réceptionniste apparaît ici : à rappeler, à chiffrer, à caler
        dans l'agenda.
      </p>
    </div>

    <UiLoader v-if="isLoading" label="Chargement des demandes…" />

    <UiEmptyState
      v-else-if="hasLoadFailed"
      title="Chargement impossible"
      description="Les demandes n'ont pas pu être chargées. Vérifiez votre connexion et réessayez."
    >
      <template #action>
        <button type="button" class="btn-secondary inline-flex items-center gap-2" @click="loadData()">
          <UIcon name="i-lucide-refresh-cw" class="h-4 w-4" />
          Réessayer
        </button>
      </template>
    </UiEmptyState>

    <template v-else>
      <div class="grid grid-cols-1 gap-4 @sm:grid-cols-3">
        <UiStatCard label="À traiter" :value="pendingRequestCount" icon="i-lucide-inbox" accent="neutral" />
        <UiStatCard label="Reçues sur 7 jours" :value="weekCount" icon="i-lucide-calendar-days" accent="neutral" />
        <UiStatCard label="Hors horaires" :value="outsideHoursLabel" icon="i-lucide-moon" accent="neutral" />
      </div>

      <section class="flex flex-col gap-3">
        <div class="flex flex-wrap items-end justify-between gap-3 border-b border-[var(--app-line)]">
          <UiFilterTabs v-model="statusTab" :tabs="statusTabs" />
          <div class="flex flex-col gap-2 pb-2 @xl:flex-row @xl:items-center">
            <div class="relative w-full @xl:w-64">
              <UIcon
                name="i-lucide-search"
                class="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-[var(--app-faint)]"
              />
              <input
                v-model="searchQuery"
                type="search"
                placeholder="Nom, contact, besoin…"
                aria-label="Rechercher une demande"
                class="app-input h-9 pl-9"
              />
            </div>
            <div class="w-full @xl:w-56">
              <UiSelectField v-model="assistantFilter" :options="assistantOptions" aria-label="Filtrer par assistant" />
            </div>
          </div>
        </div>

        <UiEmptyState
          v-if="visibleRequests.length === 0"
          :title="emptyTitle"
          description="Les demandes des visiteurs arrivent ici dès qu'ils laissent leurs coordonnées."
        />

        <template v-else>
          <ul class="app-card divide-y divide-[var(--app-line-soft)] overflow-hidden">
            <li
              v-for="request in visibleRequests"
              :key="request.id"
              class="flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-[var(--app-surface-2)] @xl:flex-row @xl:items-center @xl:gap-4"
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 cursor-pointer flex-col gap-2 text-left @xl:flex-row @xl:items-center @xl:gap-4"
                :title="`Ouvrir la demande de ${request.name}`"
                @click="openRequest(request)"
              >
                <span class="flex w-full min-w-0 items-start gap-3 @xl:w-64 @xl:shrink-0">
                  <span
                    class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)]"
                  >
                    <UIcon :name="TYPE_ICONS[request.type]" class="h-4 w-4 text-[var(--app-ink-soft)]" />
                  </span>
                  <span class="block min-w-0">
                    <span class="block truncate text-sm font-medium text-[var(--app-ink)]">{{ request.name }}</span>
                    <span class="text-muted block truncate text-xs">{{ request.contact }}</span>
                  </span>
                </span>
                <span class="block min-w-0 flex-1">
                  <span class="line-clamp-2 text-xs leading-relaxed text-[var(--app-ink-soft)] @xl:text-sm">
                    {{ request.need_summary || request.need || 'Demande de rappel, sans détail.' }}
                  </span>
                  <span class="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span class="app-badge" :class="request.type === 'urgent' ? 'app-badge--danger' : ''">
                      {{ REQUEST_TYPE_LABELS[request.type] }}
                    </span>
                    <span v-if="request.appointment_booked || request.appointment_slots.length" class="app-badge">
                      <UIcon name="i-lucide-calendar-days" class="h-3 w-3" />
                      {{ request.appointment_booked ? 'Réservé' : 'Créneaux souhaités' }}
                    </span>
                    <span v-if="request.photo_urls.length > 0" class="app-badge">
                      <UIcon name="i-lucide-camera" class="h-3 w-3" />
                      {{ request.photo_urls.length }}
                    </span>
                    <span v-if="request.received_outside_hours" class="app-badge">
                      <UIcon name="i-lucide-moon" class="h-3 w-3" />
                      Hors horaires
                    </span>
                    <span v-if="request.is_test" class="app-badge">Test</span>
                    <span class="text-muted text-xs tabular-nums">
                      {{ request.business_name }} · {{ formatShortMonthDayTime(request.created_at) }}
                    </span>
                  </span>
                </span>
              </button>
              <div class="flex shrink-0 items-center gap-2 @xl:justify-end">
                <span v-if="request.status === 'handled'" class="app-badge app-badge--success">Traitée</span>
                <span v-else-if="request.status === 'dropped'" class="app-badge">Sans suite</span>
                <button
                  v-else
                  type="button"
                  class="btn-secondary h-8 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="busyRequestId === request.id"
                  @click="markHandled(request)"
                >
                  <UIcon name="i-lucide-check" class="mr-1 h-3.5 w-3.5" />
                  Marquer traitée
                </button>
                <UIcon name="i-lucide-chevron-right" class="hidden h-4 w-4 text-[var(--app-faint)] @xl:block" />
              </div>
            </li>
          </ul>
          <p v-if="statusTab !== 'new' && allRequests.length >= REQUEST_LIST_LIMIT" class="text-muted text-xs">
            Les {{ REQUEST_LIST_LIMIT }} dernières demandes sont affichées ; l'onglet « À traiter » les montre toutes.
          </p>
        </template>
      </section>
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, ref, watch } from 'vue'
import type {
  AiAssistantListResponse,
  AiAssistantRequestItem,
  AiAssistantRequestsResponse,
  AiAssistantRequestType,
  AiAssistantSummary,
} from '~/types/AiAssistant'
import type { AssistantRequestMutationNotice } from '~/types/DrawerStack'
import type { SelectFieldOption } from '~/types/SelectField'
import type { UiFilterTab } from '~/types/UiFilterTabs'
import type { UseToastReturn } from '~/types/Composables'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useToast } from '~/composables/useToast'
import { useDrawerStackStore } from '~/stores/drawerStack'
import { REQUEST_TYPE_LABELS } from '~/utils/aiAssistantLabels'
import { formatShortMonthDayTime, parseApiDate } from '~/utils/date'

/** The inbox of the requests visitors left across the user's assistants; each row opens its drawer. */
definePageMeta({ layout: 'dashboard', middleware: 'auth' })

useSeoMeta({ title: 'Demandes — DevLeadHunter' })

const route: ReturnType<typeof useRoute> = useRoute()
const toast: UseToastReturn = useToast()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()

/** How many requests the API lists at most per call; « À traiter » is fetched apart so it is never cut. */
const REQUEST_LIST_LIMIT: number = 300

/** Icon of each request type, in the rows. */
const TYPE_ICONS: Record<AiAssistantRequestType, string> = {
  question: 'i-lucide-message-circle-question',
  quote: 'i-lucide-receipt-text',
  appointment: 'i-lucide-calendar-days',
  urgent: 'i-lucide-siren',
  other: 'i-lucide-inbox',
}

const assistants: Ref<AiAssistantSummary[]> = ref([])
/** The latest requests, every status (at most REQUEST_LIST_LIMIT). */
const allRequests: Ref<AiAssistantRequestItem[]> = ref([])
/** The requests still new, fetched apart so the tab shows them all. */
const newRequests: Ref<AiAssistantRequestItem[]> = ref([])
/** Real requests still waiting for handling (tests excluded), as counted by the API. */
const pendingRequestCount: Ref<number> = ref(0)
const isLoading: Ref<boolean> = ref(true)
const hasLoadFailed: Ref<boolean> = ref(false)
const busyRequestId: Ref<number | null> = ref(null)
const statusTab: Ref<string> = ref('new')
const searchQuery: Ref<string> = ref('')
/** Assistant id as a string for the select, « all » for every assistant. */
const assistantFilter: Ref<string> = ref(String(route.query.assistant ?? 'all'))

const statusTabs: ComputedRef<UiFilterTab[]> = computed((): UiFilterTab[] => [
  { key: 'new', label: 'À traiter', count: pendingRequestCount.value },
  { key: 'all', label: 'Toutes', count: allRequests.value.length },
  { key: 'handled', label: 'Traitées' },
  { key: 'dropped', label: 'Sans suite' },
])

const assistantOptions: ComputedRef<SelectFieldOption[]> = computed((): SelectFieldOption[] => [
  { value: 'all', label: 'Tous les assistants' },
  ...assistants.value.map(
    (assistant: AiAssistantSummary): SelectFieldOption => ({
      value: String(assistant.id),
      label: assistant.business_name,
    }),
  ),
])

/** Requests received over the last 7 days (tests excluded). */
const weekCount: ComputedRef<number> = computed((): number => {
  const since: number = Date.now() - 7 * 24 * 3600 * 1000
  return allRequests.value.filter(
    (request: AiAssistantRequestItem): boolean =>
      !request.is_test && parseApiDate(request.created_at).getTime() >= since,
  ).length
})

/** Share of the listed requests received outside the business hours (« 31 % »), or a dash. */
const outsideHoursLabel: ComputedRef<string> = computed((): string => {
  const known: AiAssistantRequestItem[] = allRequests.value.filter(
    (request: AiAssistantRequestItem): boolean => !request.is_test && request.received_outside_hours !== null,
  )
  if (known.length === 0) return '—'
  const outside: number = known.filter((request: AiAssistantRequestItem): boolean =>
    Boolean(request.received_outside_hours),
  ).length
  return `${Math.round((outside / known.length) * 100)} %`
})

/** The list behind the active tab, before the assistant and search filters. */
const tabRequests: ComputedRef<AiAssistantRequestItem[]> = computed((): AiAssistantRequestItem[] => {
  if (statusTab.value === 'new') {
    return newRequests.value.filter((request: AiAssistantRequestItem): boolean => !request.is_test)
  }
  if (statusTab.value === 'all') return allRequests.value
  return allRequests.value.filter((request: AiAssistantRequestItem): boolean => request.status === statusTab.value)
})

const visibleRequests: ComputedRef<AiAssistantRequestItem[]> = computed((): AiAssistantRequestItem[] => {
  let result: AiAssistantRequestItem[] = tabRequests.value
  if (assistantFilter.value !== 'all') {
    const assistantId: number = Number(assistantFilter.value)
    result = result.filter((request: AiAssistantRequestItem): boolean => request.assistant_id === assistantId)
  }
  const query: string = searchQuery.value.trim().toLowerCase()
  if (query) {
    result = result.filter((request: AiAssistantRequestItem): boolean =>
      [request.name, request.contact, request.need ?? '', request.need_summary ?? '', request.business_name].some(
        (field: string): boolean => field.toLowerCase().includes(query),
      ),
    )
  }
  return result
})

const emptyTitle: ComputedRef<string> = computed((): string => {
  if (searchQuery.value.trim() || assistantFilter.value !== 'all') return 'Aucune demande ne correspond'
  if (statusTab.value === 'new') return 'Aucune demande à traiter'
  return 'Aucune demande pour le moment'
})

/**
 * Open a request in its drawer.
 * @param request - The request.
 */
function openRequest(request: AiAssistantRequestItem): void {
  drawerStack.push({ kind: 'assistant-request', request })
}

/**
 * Mark a request handled from its row, without opening it.
 * @param request - The request.
 * @returns A promise resolved once saved.
 */
async function markHandled(request: AiAssistantRequestItem): Promise<void> {
  busyRequestId.value = request.id
  try {
    const updated: AiAssistantRequestItem = await AiAssistantService.updateRequest(request.id, { status: 'handled' })
    // Through the store: an open drawer of this request refreshes, and the watcher below applies it here.
    drawerStack.notifyAssistantRequestUpdated(updated)
  } catch {
    toast.error('Mise à jour de la demande impossible.')
  } finally {
    busyRequestId.value = null
  }
}

/**
 * Refresh one request in both lists and the pending count.
 * @param updated - The request as the API returned it.
 */
function applyUpdate(updated: AiAssistantRequestItem): void {
  const previous: AiAssistantRequestItem | undefined =
    allRequests.value.find((item: AiAssistantRequestItem): boolean => item.id === updated.id) ??
    newRequests.value.find((item: AiAssistantRequestItem): boolean => item.id === updated.id)
  allRequests.value = allRequests.value.map(
    (item: AiAssistantRequestItem): AiAssistantRequestItem => (item.id === updated.id ? updated : item),
  )
  const others: AiAssistantRequestItem[] = newRequests.value.filter(
    (item: AiAssistantRequestItem): boolean => item.id !== updated.id,
  )
  newRequests.value = updated.status === 'new' ? [updated, ...others] : others
  if (previous && !updated.is_test) {
    pendingRequestCount.value += Number(updated.status === 'new') - Number(previous.status === 'new')
  }
}

/**
 * Load the assistants (for the filter) and the requests: the latest ones, and every one still new.
 * @returns A promise resolved once loaded.
 */
async function loadData(): Promise<void> {
  isLoading.value = true
  hasLoadFailed.value = false
  try {
    const [list, requests, pendingList]: [
      AiAssistantListResponse,
      AiAssistantRequestsResponse,
      AiAssistantRequestsResponse,
    ] = await Promise.all([
      AiAssistantService.list(),
      AiAssistantService.listRequests(),
      AiAssistantService.listRequests('new'),
    ])
    assistants.value = list.assistants
    allRequests.value = requests.requests
    newRequests.value = pendingList.requests
    pendingRequestCount.value = requests.pending_count
  } catch {
    hasLoadFailed.value = true
  } finally {
    isLoading.value = false
  }
}

watch(
  (): number => drawerStack.requestMutationCounter,
  (): void => {
    const notice: AssistantRequestMutationNotice | null = drawerStack.lastRequestMutation
    if (notice?.type === 'updated') applyUpdate(notice.request)
  },
)

watch(
  (): string => String(route.query.assistant ?? 'all'),
  (assistantId: string): void => {
    assistantFilter.value = assistantId
  },
)

onMounted(async (): Promise<void> => {
  await loadData()
})
</script>
