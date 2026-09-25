<template>
  <div>
    <div class="mb-8 flex flex-col gap-4 @2xl:flex-row @2xl:items-end @2xl:justify-between">
      <div>
        <p class="text-xs font-semibold tracking-wider text-[var(--app-ink-soft)] uppercase">Module IA</p>
        <h1 class="app-page-title mt-1">Assistants IA</h1>
        <p class="mt-2 max-w-xl text-sm text-[var(--app-ink-soft)]">
          Les réceptionnistes générées pour vos prospects : la démo à envoyer, le script à coller sur leur site, et ce
          qu'elles captent pour vous.
        </p>
      </div>
      <NuxtLink to="/dashboard/ai-assistants/requests" class="btn-primary inline-flex w-fit items-center gap-2">
        <UIcon name="i-lucide-inbox" class="h-4 w-4" />
        Demandes à traiter
        <span v-if="pendingRequestCount > 0" class="rounded-full bg-[var(--app-bg)]/20 px-1.5 text-[11px] tabular-nums">
          {{ pendingRequestCount }}
        </span>
      </NuxtLink>
    </div>

    <div v-if="pending" class="grid gap-4 @2xl:grid-cols-2 @5xl:grid-cols-3">
      <div v-for="i in 3" :key="i" class="card animate-pulse">
        <div class="h-40 bg-[var(--app-surface-2)]"></div>
        <div class="space-y-3 p-5">
          <div class="h-4 w-2/3 rounded bg-[var(--app-surface-2)]"></div>
          <div class="h-3 w-1/2 rounded bg-[var(--app-surface-2)]"></div>
        </div>
      </div>
    </div>

    <UiEmptyState
      v-else-if="hasLoadFailed"
      title="Chargement impossible"
      description="Les assistants n'ont pas pu être chargés. Vérifiez votre connexion et réessayez."
    >
      <template #action>
        <button type="button" class="btn-secondary inline-flex items-center gap-2" @click="loadData()">
          <UIcon name="i-lucide-refresh-cw" class="h-4 w-4" />
          Réessayer
        </button>
      </template>
    </UiEmptyState>

    <div v-else-if="!assistants.length" class="card flex flex-col items-center justify-center px-8 py-16 text-center">
      <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--app-surface-2)]/50">
        <UIcon name="i-lucide-bot" class="h-6 w-6 text-[var(--app-ink-soft)]" />
      </div>
      <h2 class="text-lg font-semibold text-[var(--app-ink)]">Aucun assistant généré</h2>
      <p class="mt-2 max-w-sm text-sm text-[var(--app-ink-soft)]">
        Ouvrez un prospect et cliquez « Générer un assistant IA » : sa démo est prête en une minute.
      </p>
      <NuxtLink to="/dashboard/my-prospects" class="btn-primary mt-6 inline-flex items-center gap-2">
        <UIcon name="i-lucide-users" class="h-4 w-4" />
        Voir mes prospects
      </NuxtLink>
    </div>

    <template v-else>
      <div class="mb-6 grid grid-cols-1 gap-4 @sm:grid-cols-3">
        <UiStatCard label="Démos en ligne" :value="activeCount" icon="i-lucide-bot" accent="neutral" />
        <UiStatCard label="Vendus" :value="deliveredCount" icon="i-lucide-badge-check" accent="neutral" />
        <UiStatCard label="Demandes à traiter" :value="pendingRequestCount" icon="i-lucide-inbox" accent="neutral" />
      </div>

      <div class="mb-5 flex flex-col gap-3 @2xl:flex-row @2xl:items-center @2xl:justify-between">
        <div class="relative w-full @2xl:max-w-xs">
          <UIcon
            name="i-lucide-search"
            class="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-[var(--app-faint)]"
          />
          <input
            v-model="searchQuery"
            type="search"
            placeholder="Entreprise, prénom de l'assistant…"
            aria-label="Rechercher un assistant"
            class="app-input pl-9"
          />
        </div>
        <div class="w-full @2xl:w-56">
          <UiSelectField v-model="statusFilter" :options="STATUS_FILTER_OPTIONS" aria-label="Filtrer par statut" />
        </div>
      </div>

      <p v-if="hasActiveFilters" class="mb-4 flex flex-wrap items-center gap-2 text-xs text-[var(--app-ink-soft)]">
        <UIcon name="i-lucide-filter" class="h-3 w-3" />
        {{ filteredAssistants.length }} sur {{ assistants.length }} assistants
        <button
          type="button"
          class="cursor-pointer font-medium underline underline-offset-2 hover:text-[var(--app-ink)]"
          @click="clearFilters"
        >
          Tout afficher
        </button>
      </p>

      <div v-if="filteredAssistants.length" class="grid gap-5 @2xl:grid-cols-2 @5xl:grid-cols-3">
        <AssistantCard
          v-for="assistant in filteredAssistants"
          :key="assistant.id"
          :assistant="assistant"
          @copy="copyDemoUrl"
          @open="openDemoUrl"
        />
      </div>

      <div v-else class="card flex flex-col items-center justify-center px-8 py-16 text-center">
        <div class="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--app-surface-2)]/50">
          <UIcon name="i-lucide-search-x" class="h-6 w-6 text-[var(--app-ink-soft)]" />
        </div>
        <h2 class="text-lg font-semibold text-[var(--app-ink)]">Aucun assistant ne correspond</h2>
        <p class="mt-2 max-w-sm text-sm text-[var(--app-ink-soft)]">
          Aucun assistant ne correspond à votre recherche ou au statut sélectionné.
        </p>
        <button type="button" class="btn-secondary mt-6 inline-flex items-center gap-2" @click="clearFilters">
          <UIcon name="i-lucide-rotate-ccw" class="h-4 w-4" />
          Réinitialiser les filtres
        </button>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, ref, watch } from 'vue'
import type { UseCopyToClipboardReturn, UseOpenExternalUrlReturn } from '~/types/Composables'
import type { AiAssistantListResponse, AiAssistantRequestsResponse, AiAssistantSummary } from '~/types/AiAssistant'
import type { AssistantMutationNotice } from '~/types/DrawerStack'
import type { SelectFieldOption } from '~/types/SelectField'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useDrawerStackStore } from '~/stores/drawerStack'

/**
 * The assistants generated for the user's prospects, as cards with a live preview of their demo page.
 * Generation happens from a prospect; each card opens the assistant's detail page.
 */
definePageMeta({ layout: 'dashboard', middleware: 'auth' })

useSeoMeta({ title: 'Assistants IA — DevLeadHunter' })

const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()
const { copy }: UseCopyToClipboardReturn = useCopyToClipboard()
const { openExternalUrl }: UseOpenExternalUrlReturn = useOpenExternalUrl()

const assistants: Ref<AiAssistantSummary[]> = ref([])
/** Real requests still waiting for handling (tests excluded), as counted by the API. */
const pendingRequestCount: Ref<number> = ref(0)
const pending: Ref<boolean> = ref(true)
const hasLoadFailed: Ref<boolean> = ref(false)
const searchQuery: Ref<string> = ref('')
const statusFilter: Ref<string> = ref('all')

/** Status filter options, in the order a seller thinks of them. */
const STATUS_FILTER_OPTIONS: SelectFieldOption[] = [
  { value: 'all', label: 'Tous les statuts' },
  { value: 'active', label: 'Démo en ligne' },
  { value: 'delivered', label: 'Vendu' },
  { value: 'expired', label: 'Expiré' },
]

const activeCount: ComputedRef<number> = computed(
  (): number => assistants.value.filter((item: AiAssistantSummary): boolean => item.status === 'active').length,
)

const deliveredCount: ComputedRef<number> = computed(
  (): number => assistants.value.filter((item: AiAssistantSummary): boolean => item.status === 'delivered').length,
)

/** Assistants matching both the search query and the status filter. */
const filteredAssistants: ComputedRef<AiAssistantSummary[]> = computed((): AiAssistantSummary[] => {
  let result: AiAssistantSummary[] = assistants.value
  if (statusFilter.value !== 'all') {
    result = result.filter((item: AiAssistantSummary): boolean => item.status === statusFilter.value)
  }
  const query: string = searchQuery.value.trim().toLowerCase()
  if (query) {
    result = result.filter(
      (item: AiAssistantSummary): boolean =>
        item.business_name.toLowerCase().includes(query) || item.assistant_name.toLowerCase().includes(query),
    )
  }
  return result
})

const hasActiveFilters: ComputedRef<boolean> = computed(
  (): boolean => searchQuery.value.trim() !== '' || statusFilter.value !== 'all',
)

/**
 * Open a demo page in a new tab.
 * @param url - The demo URL, internal marker included.
 * @returns A promise resolved once opened.
 */
async function openDemoUrl(url: string): Promise<void> {
  await openExternalUrl(url)
}

/**
 * Copy a demo URL to the clipboard.
 * @param url - The public demo URL.
 * @returns A promise resolved once copied.
 */
async function copyDemoUrl(url: string): Promise<void> {
  await copy(url)
}

/** Reset the search field and the status filter so every assistant shows again. */
function clearFilters(): void {
  searchQuery.value = ''
  statusFilter.value = 'all'
}

/**
 * Load the assistants and how many requests wait for handling.
 * @returns A promise resolved once loaded.
 */
async function loadData(): Promise<void> {
  pending.value = true
  hasLoadFailed.value = false
  try {
    const [list, requests]: [AiAssistantListResponse, AiAssistantRequestsResponse] = await Promise.all([
      AiAssistantService.list(),
      AiAssistantService.listRequests('new'),
    ])
    assistants.value = list.assistants
    pendingRequestCount.value = requests.pending_count
  } catch {
    hasLoadFailed.value = true
  } finally {
    pending.value = false
  }
}

watch(
  (): number => drawerStack.assistantMutationCounter,
  (): void => {
    const notice: AssistantMutationNotice | null = drawerStack.lastAssistantMutation
    if (notice?.type === 'updated') {
      assistants.value = assistants.value.map(
        (item: AiAssistantSummary): AiAssistantSummary => (item.id === notice.assistant.id ? notice.assistant : item),
      )
    } else if (notice?.type === 'deleted') {
      assistants.value = assistants.value.filter((item: AiAssistantSummary): boolean => item.id !== notice.assistantId)
    }
  },
)

onMounted(async (): Promise<void> => {
  await loadData()
})
</script>
