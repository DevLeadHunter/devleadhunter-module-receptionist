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
        <div
          class="flex flex-col gap-3 border-b border-[var(--app-line)] @xl:flex-row @xl:items-end @xl:justify-between"
        >
          <UiFilterTabs v-model="statusTab" :tabs="statusTabs" />
          <div class="flex w-full flex-col gap-2 pb-3 @xl:w-auto @xl:flex-row @xl:items-center @xl:pb-2">
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
          <div class="app-card overflow-hidden">
            <BaseTable min-width="760px">
              <template #head>
                <BaseTableTh>Visiteur</BaseTableTh>
                <BaseTableTh>Demande</BaseTableTh>
                <BaseTableTh>Assistant</BaseTableTh>
                <BaseTableTh align="right">Reçue</BaseTableTh>
                <BaseTableTh align="center">Statut</BaseTableTh>
              </template>

              <BaseTableTr
                v-for="request in visibleRequests"
                :key="request.id"
                class="cursor-pointer"
                tabindex="0"
                @click="openRequest(request)"
                @keydown.enter="openRequest(request)"
              >
                <BaseTableTd>
                  <span class="block text-sm font-semibold text-[var(--app-ink)]">{{ request.name }}</span>
                  <span class="font-label text-xs whitespace-nowrap text-[var(--app-ink-soft)]">{{
                    request.contact
                  }}</span>
                </BaseTableTd>

                <BaseTableTd label="Demande">
                  <span class="block min-w-0 text-left">
                    <span class="flex items-start gap-2">
                      <span
                        class="app-badge mt-0.5 shrink-0"
                        :class="request.type === 'urgent' ? 'app-badge--danger' : ''"
                      >
                        {{ REQUEST_TYPE_LABELS[request.type] }}
                      </span>
                      <span class="line-clamp-2 text-sm leading-relaxed text-[var(--app-ink)]">
                        {{ requestSummary(request) }}
                      </span>
                    </span>
                    <span
                      v-if="requestFlags(request).length > 0"
                      class="mt-1.5 flex items-center gap-2 text-[var(--app-faint)]"
                    >
                      <UIcon
                        v-for="flag in requestFlags(request)"
                        :key="flag.icon"
                        :name="flag.icon"
                        class="h-3.5 w-3.5"
                        role="img"
                        :aria-label="flag.label"
                        :title="flag.label"
                      />
                    </span>
                  </span>
                </BaseTableTd>

                <BaseTableTd label="Assistant" class="text-sm text-[var(--app-ink-soft)]">
                  {{ request.business_name }}
                </BaseTableTd>

                <BaseTableTd
                  label="Reçue"
                  align="right"
                  class="font-label text-xs whitespace-nowrap text-[var(--app-ink-soft)]"
                >
                  {{ formatShortMonthDayTime(request.created_at) }}
                </BaseTableTd>

                <BaseTableTd label="Statut" align="center">
                  <span :class="['app-badge', REQUEST_STATUS_BADGE_CLASS[request.status]]">
                    {{ REQUEST_STATUS_LABELS[request.status] }}
                  </span>
                </BaseTableTd>
              </BaseTableTr>
            </BaseTable>
          </div>
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
  AiAssistantRequestStatus,
  AiAssistantSummary,
} from '~/types/AiAssistant'
import type { AiAssistantRequestFlag } from '~/types/AiAssistantRequestsPage'
import type { AssistantRequestMutationNotice } from '~/types/DrawerStack'
import type { SelectFieldOption } from '~/types/SelectField'
import type { UiFilterTab } from '~/types/UiFilterTabs'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useDrawerStackStore } from '~/stores/drawerStack'
import { REQUEST_STATUS_LABELS, REQUEST_TYPE_LABELS } from '~/utils/aiAssistantLabels'
import { formatShortMonthDayTime, parseApiDate } from '~/utils/date'

/** The inbox of the requests visitors left across the user's assistants; each row opens its drawer. */
definePageMeta({ layout: 'dashboard', middleware: ['auth', 'ai-assistant-module'] })

useSeoMeta({ title: 'Demandes — DevLeadHunter' })

const route: ReturnType<typeof useRoute> = useRoute()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()

/** How many requests the API lists at most per call; « À traiter » is fetched apart so it is never cut. */
const REQUEST_LIST_LIMIT: number = 300

/** Badge tone of each request status: the ones still waiting stand out. */
const REQUEST_STATUS_BADGE_CLASS: Record<AiAssistantRequestStatus, string> = {
  new: 'app-badge--strong',
  handled: 'app-badge--success',
  dropped: '',
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
 * One line for what the visitor needs: the analyser's summary, else their own words.
 * @param request - The request.
 * @returns The summary, or a fallback for a plain call-back.
 */
function requestSummary(request: AiAssistantRequestItem): string {
  return request.need_summary || request.need || 'Demande de rappel, sans détail.'
}

/**
 * The marks worth a glance in the list: slot wished or booked, photos, outside hours, test.
 * @param request - The request.
 * @returns The icons to show, each with its label.
 */
function requestFlags(request: AiAssistantRequestItem): AiAssistantRequestFlag[] {
  const flags: AiAssistantRequestFlag[] = []
  if (request.appointment_booked) flags.push({ icon: 'i-lucide-calendar-check', label: 'Rendez-vous réservé' })
  else if (request.appointment_slots.length > 0) {
    flags.push({ icon: 'i-lucide-calendar-days', label: 'Créneaux souhaités' })
  }
  if (request.photo_urls.length > 0) {
    flags.push({ icon: 'i-lucide-camera', label: `${request.photo_urls.length} photo(s) jointe(s)` })
  }
  if (request.received_outside_hours) flags.push({ icon: 'i-lucide-moon', label: 'Reçue hors horaires' })
  if (request.is_test) flags.push({ icon: 'i-lucide-flask-conical', label: 'Demande de test' })
  return flags
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
