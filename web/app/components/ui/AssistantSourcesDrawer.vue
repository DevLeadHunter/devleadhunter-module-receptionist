<template>
  <Teleport to="body">
    <Transition name="drawer-panel">
      <div
        v-if="open && assistant"
        class="fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[520px] flex-col border-l border-[var(--app-line)] bg-[var(--app-surface)] pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
      >
        <div class="flex items-start gap-3 border-b border-[var(--app-line)] px-5 py-4">
          <button
            v-if="showBack"
            type="button"
            class="flex h-10 w-7 shrink-0 items-center justify-center rounded text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
            title="Revenir au volet précédent"
            aria-label="Revenir au volet précédent"
            @click="emit('back')"
          >
            <UIcon name="i-lucide-chevron-left" class="h-4 w-4" />
          </button>
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)]"
          >
            <UIcon name="i-lucide-library" class="h-4 w-4 text-[var(--app-ink-soft)]" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 class="truncate text-base leading-tight font-semibold text-[var(--app-ink)]">
              Ce que {{ assistant.assistant_name }} lit
            </h2>
            <p class="text-muted mt-0.5 truncate text-sm">{{ assistant.business_name }}</p>
          </div>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
            aria-label="Fermer"
            @click="emit('close')"
          >
            <UIcon name="i-lucide-x" class="h-4 w-4" />
          </button>
        </div>

        <div class="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          <p v-if="isLoading && !sources" class="text-muted text-sm">Chargement…</p>

          <template v-else-if="sources">
            <section class="flex flex-col gap-2">
              <div class="flex items-center justify-between gap-3">
                <h3 class="app-label !text-[0.6rem]">Site web</h3>
                <UiSwitch
                  id="assistant-source-site"
                  :model-value="sources.site_enabled"
                  label="Lu par l'assistant"
                  :disabled="isBusy"
                  @update:model-value="toggleSource('site_enabled', $event)"
                />
              </div>
              <p v-if="!sources.website_url" class="text-muted text-sm">Aucun site connu pour ce commerce.</p>
              <template v-else>
                <a
                  :href="sources.website_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="truncate text-sm text-[var(--app-ink)] underline underline-offset-2"
                >
                  {{ sources.website_url }}
                </a>
                <p class="text-muted text-xs leading-relaxed">{{ syncLine }}</p>
                <ul class="flex flex-col gap-1">
                  <li
                    v-for="page in sources.pages"
                    :key="page.url"
                    class="flex items-center justify-between gap-3 text-xs"
                    :class="{ 'opacity-50': !sources.site_enabled }"
                  >
                    <span class="truncate text-[var(--app-ink)]" :title="page.url">{{ page.title || page.url }}</span>
                    <span class="text-muted shrink-0 tabular-nums">{{ formatChars(page.chars) }}</span>
                  </li>
                </ul>
                <button
                  type="button"
                  class="btn-secondary h-8 self-start text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isBusy"
                  @click="refreshWebsite"
                >
                  <UIcon
                    name="i-lucide-refresh-cw"
                    class="mr-1 h-3.5 w-3.5"
                    :class="{ 'animate-spin': isRefreshing }"
                  />
                  {{ isRefreshing ? 'Lecture du site…' : 'Mettre à jour' }}
                </button>
              </template>
            </section>

            <section class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-4">
              <div class="flex items-center justify-between gap-3">
                <h3 class="app-label !text-[0.6rem]">Fiche Google</h3>
                <UiSwitch
                  id="assistant-source-listing"
                  :model-value="sources.listing_enabled"
                  label="Lue par l'assistant"
                  :disabled="isBusy"
                  @update:model-value="toggleSource('listing_enabled', $event)"
                />
              </div>
              <p class="text-muted text-xs leading-relaxed">
                {{
                  sources.listing_facts.length > 0
                    ? sources.listing_facts.join(' · ')
                    : 'Rien de plus que le nom du commerce.'
                }}
              </p>
            </section>

            <section class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-4">
              <div class="flex items-center justify-between gap-3">
                <h3 class="app-label !text-[0.6rem]">
                  Documents ({{ sources.documents.length }}/{{ sources.max_documents }})
                </h3>
                <button
                  type="button"
                  class="btn-secondary h-8 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isBusy || sources.documents.length >= sources.max_documents"
                  @click="fileInput?.click()"
                >
                  <UIcon name="i-lucide-file-up" class="mr-1 h-3.5 w-3.5" />
                  {{ isUploading ? 'Lecture du PDF…' : 'Ajouter un PDF' }}
                </button>
                <input
                  ref="fileInput"
                  type="file"
                  accept="application/pdf,.pdf"
                  class="hidden"
                  @change="uploadDocument"
                />
              </div>
              <p v-if="sources.documents.length === 0" class="text-muted text-xs leading-relaxed">
                Tarifs, conditions de vente, plaquette, FAQ : un PDF de 10 Mo au plus, avec du texte (pas un scan).
                L'assistant s'en sert pour répondre et cite le document.
              </p>
              <ul v-else class="flex flex-col gap-2">
                <li
                  v-for="document in sources.documents"
                  :key="document.id"
                  class="flex flex-col gap-1.5 rounded-md border border-[var(--app-line)] px-3 py-2"
                >
                  <div class="flex items-center justify-between gap-3">
                    <a
                      v-if="document.url"
                      :href="document.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="truncate text-sm font-medium text-[var(--app-ink)] underline-offset-2 hover:underline"
                    >
                      {{ document.name }}
                    </a>
                    <span v-else class="truncate text-sm font-medium text-[var(--app-ink)]">{{ document.name }}</span>
                    <UiSwitch
                      :id="`assistant-document-${document.id}`"
                      :model-value="document.enabled"
                      label="Lu"
                      :disabled="isBusy"
                      @update:model-value="toggleDocument(document, $event)"
                    />
                  </div>
                  <div class="flex items-center justify-between gap-3 text-xs">
                    <span class="text-muted">{{ documentMeta(document) }}</span>
                    <button
                      type="button"
                      class="text-muted cursor-pointer transition-colors hover:text-[var(--app-ink)] disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="isBusy"
                      @click="askDelete(document)"
                    >
                      Supprimer
                    </button>
                  </div>
                </li>
              </ul>
            </section>
          </template>

          <div v-else-if="hasLoadFailed" class="flex flex-col items-start gap-2">
            <p class="text-muted text-sm">Sources indisponibles pour le moment.</p>
            <button type="button" class="btn-secondary h-8 text-xs" @click="assistant && loadSources(assistant.id)">
              <UIcon name="i-lucide-refresh-cw" class="mr-1 h-3.5 w-3.5" />
              Réessayer
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <UiConfirmModal
      v-if="open && assistant"
      ref="confirmModal"
      title="Supprimer le document"
      :message="`Supprimer « ${documentToDelete?.name} » ? L'assistant ne le lira plus et le fichier sera effacé.`"
      confirm-text="Supprimer"
      cancel-text="Annuler"
      @confirm="deleteDocument"
    />
  </Teleport>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AiAssistantSummary } from '~/types/AiAssistant'
import type { AiAssistantDocumentItem, AiAssistantSources, AiAssistantSourcesUpdate } from '~/types/AiAssistantSources'
import type { UseToastReturn } from '~/types/Composables'
import type { UiAssistantSourcesDrawerEmits, UiAssistantSourcesDrawerProps } from '~/types/UiAssistantSourcesDrawer'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useToast } from '~/composables/useToast'
import { formatNumericDateTime } from '~/utils/date'

/** What an assistant reads — website, Google listing, documents — with a switch per source. */
const props: UiAssistantSourcesDrawerProps = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  assistant: {
    type: Object as PropType<AiAssistantSummary | null>,
    default: null,
  },
  showBack: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<UiAssistantSourcesDrawerEmits> = defineEmits<UiAssistantSourcesDrawerEmits>()

/** The API refuses a PDF above this size before reading it. */
const MAX_DOCUMENT_BYTES: number = 10 * 1024 * 1024

const toast: UseToastReturn = useToast()
const sources: Ref<AiAssistantSources | null> = ref(null)
const loadingAssistantId: Ref<number | null> = ref(null)
const isRefreshing: Ref<boolean> = ref(false)
const isUploading: Ref<boolean> = ref(false)
const isSaving: Ref<boolean> = ref(false)
const hasLoadFailed: Ref<boolean> = ref(false)
/** Document waiting for the deletion to be confirmed. */
const documentToDelete: Ref<AiAssistantDocumentItem | null> = ref(null)
/** Confirm modal handle. */
const confirmModal: Ref<{ open: () => void } | null> = ref(null)
const fileInput: Ref<HTMLInputElement | null> = ref(null)

const isLoading: ComputedRef<boolean> = computed((): boolean => loadingAssistantId.value !== null)

const isBusy: ComputedRef<boolean> = computed(
  (): boolean => isLoading.value || isRefreshing.value || isUploading.value || isSaving.value,
)

/** « Lu le 24/09/2026 à 10:05 : 3 pages modifiées (1 ajoutée, 2 changées). » */
const syncLine: ComputedRef<string> = computed((): string => {
  const sync: AiAssistantSources['sync'] = sources.value?.sync ?? null
  const pageCount: number = sources.value?.pages.length ?? 0
  if (!sync?.at) {
    if (pageCount === 0) return "Aucune page lue pour l'instant : « Mettre à jour » lit le site."
    return `${pageCount} page${pageCount > 1 ? 's' : ''} lue${pageCount > 1 ? 's' : ''} à la création de l'assistant.`
  }
  const when: string = `Lu le ${formatNumericDateTime(sync.at)}`
  if (sync.error) return `${when} : ${sync.error}`
  const total: number = sync.added.length + sync.removed.length + sync.changed.length
  if (total === 0) return `${when} : aucun changement.`
  const parts: string[] = [
    plural(sync.added.length, 'ajoutée', 'ajoutées'),
    plural(sync.changed.length, 'changée', 'changées'),
    plural(sync.removed.length, 'retirée', 'retirées'),
  ].filter((part: string): boolean => part !== '')
  return `${when} : ${total} page${total > 1 ? 's' : ''} modifiée${total > 1 ? 's' : ''} (${parts.join(', ')}).`
})

/**
 * « 2 changées », or nothing for zero.
 * @param count - How many.
 * @param singular - The word for one.
 * @param pluralWord - The word for several.
 * @returns The count and its word, or an empty string.
 */
function plural(count: number, singular: string, pluralWord: string): string {
  if (count === 0) return ''
  return `${count} ${count > 1 ? pluralWord : singular}`
}

/**
 * A text size as the operator reads it (« 3 200 caractères »).
 * @param chars - The number of characters.
 * @returns The label.
 */
function formatChars(chars: number): string {
  return `${chars.toLocaleString('fr-FR')} caractères`
}

/**
 * Pages, size and cut of a document (« 3 pages · 12 000 caractères · coupé »).
 * @param document - The document.
 * @returns The label.
 */
function documentMeta(document: AiAssistantDocumentItem): string {
  const bits: string[] = [`${document.pages} page${document.pages > 1 ? 's' : ''}`, formatChars(document.chars)]
  if (document.truncated) bits.push('texte coupé')
  if (!document.enabled) bits.push('non lu')
  return bits.join(' · ')
}

/**
 * Whether a reply still belongs to the drawer on screen: not closed, not switched to another assistant meanwhile.
 * @param assistantId - The assistant the request was made for.
 * @returns True when the reply may update the drawer.
 */
function isShowing(assistantId: number): boolean {
  return props.open && props.assistant?.id === assistantId
}

/**
 * Load the assistant's sources.
 * @param assistantId - The assistant.
 * @returns A promise resolved once loaded.
 */
async function loadSources(assistantId: number): Promise<void> {
  loadingAssistantId.value = assistantId
  hasLoadFailed.value = false
  try {
    const loaded: AiAssistantSources = await AiAssistantService.getSources(assistantId)
    if (isShowing(assistantId)) sources.value = loaded
  } catch {
    if (isShowing(assistantId)) hasLoadFailed.value = true
  } finally {
    if (loadingAssistantId.value === assistantId) loadingAssistantId.value = null
  }
}

/**
 * Switch the website or the Google listing on or off.
 * @param key - The switch.
 * @param enabled - Its new value.
 * @returns A promise resolved once saved.
 */
async function toggleSource(key: keyof AiAssistantSourcesUpdate, enabled: boolean): Promise<void> {
  if (!props.assistant) return
  const assistantId: number = props.assistant.id
  isSaving.value = true
  try {
    const updated: AiAssistantSources = await AiAssistantService.updateSources(assistantId, { [key]: enabled })
    if (isShowing(assistantId)) sources.value = updated
  } catch {
    toast.error('Changement impossible, réessayez.')
  } finally {
    isSaving.value = false
  }
}

/**
 * Read the website again now.
 * @returns A promise resolved once read.
 */
async function refreshWebsite(): Promise<void> {
  if (!props.assistant) return
  const assistantId: number = props.assistant.id
  isRefreshing.value = true
  try {
    const refreshed: AiAssistantSources = await AiAssistantService.refreshWebsite(assistantId)
    if (!isShowing(assistantId)) return
    sources.value = refreshed
    if (refreshed.sync?.error) toast.error(syncLine.value)
    else toast.success(syncLine.value)
  } catch {
    toast.error('Lecture du site impossible pour le moment.')
  } finally {
    isRefreshing.value = false
  }
}

/**
 * Send the picked PDF to the assistant.
 * @param event - The file input's change.
 * @returns A promise resolved once stored or refused.
 */
async function uploadDocument(event: Event): Promise<void> {
  const input: HTMLInputElement = event.target as HTMLInputElement
  const file: File | undefined = input.files?.[0]
  input.value = ''
  if (!file || !props.assistant || !sources.value) return
  if (!isPdf(file)) {
    toast.error('Seul un PDF est accepté.')
    return
  }
  if (file.size > MAX_DOCUMENT_BYTES) {
    toast.error('Ce PDF dépasse 10 Mo.')
    return
  }
  const assistantId: number = props.assistant.id
  isUploading.value = true
  try {
    const document: AiAssistantDocumentItem = await AiAssistantService.uploadDocument(assistantId, file)
    if (isShowing(assistantId) && sources.value) {
      sources.value = { ...sources.value, documents: [...sources.value.documents, document] }
    }
    toast.success(`« ${document.name} » est lu par l'assistant.`)
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Envoi du document impossible.')
  } finally {
    isUploading.value = false
  }
}

/**
 * Switch a document on or off.
 * @param document - The document.
 * @param enabled - Whether the assistant reads it.
 * @returns A promise resolved once saved.
 */
async function toggleDocument(document: AiAssistantDocumentItem, enabled: boolean): Promise<void> {
  if (!props.assistant || !sources.value) return
  const assistantId: number = props.assistant.id
  isSaving.value = true
  try {
    const updated: AiAssistantDocumentItem = await AiAssistantService.setDocumentEnabled(
      assistantId,
      document.id,
      enabled,
    )
    if (!isShowing(assistantId) || !sources.value) return
    sources.value = {
      ...sources.value,
      documents: sources.value.documents.map(
        (item: AiAssistantDocumentItem): AiAssistantDocumentItem => (item.id === updated.id ? updated : item),
      ),
    }
  } catch {
    toast.error('Changement impossible, réessayez.')
  } finally {
    isSaving.value = false
  }
}

/**
 * Whether a picked file is a PDF, by type or by name (some browsers leave the type empty).
 * @param file - The picked file.
 * @returns True for a PDF.
 */
function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

/**
 * Ask to confirm the deletion of a document.
 * @param document - The document.
 */
function askDelete(document: AiAssistantDocumentItem): void {
  documentToDelete.value = document
  confirmModal.value?.open()
}

/**
 * Delete the confirmed document and its file.
 * @returns A promise resolved once deleted.
 */
async function deleteDocument(): Promise<void> {
  const document: AiAssistantDocumentItem | null = documentToDelete.value
  if (!document || !props.assistant || !sources.value) return
  const assistantId: number = props.assistant.id
  isSaving.value = true
  try {
    await AiAssistantService.deleteDocument(assistantId, document.id)
    if (!isShowing(assistantId) || !sources.value) return
    sources.value = {
      ...sources.value,
      documents: sources.value.documents.filter((item: AiAssistantDocumentItem): boolean => item.id !== document.id),
    }
    documentToDelete.value = null
  } catch {
    toast.error('Suppression impossible, réessayez.')
  } finally {
    isSaving.value = false
  }
}

watch(
  (): number | null => (props.open && props.assistant ? props.assistant.id : null),
  (assistantId: number | null): void => {
    // Another assistant, or a closed drawer: what the previous one was doing must not lock this one.
    sources.value = null
    documentToDelete.value = null
    isRefreshing.value = false
    isUploading.value = false
    isSaving.value = false
    hasLoadFailed.value = false
    if (assistantId !== null) void loadSources(assistantId)
  },
  { immediate: true },
)
</script>

<style scoped>
.drawer-panel-enter-active,
.drawer-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.drawer-panel-enter-from,
.drawer-panel-leave-to {
  transform: translateX(100%);
}
</style>
