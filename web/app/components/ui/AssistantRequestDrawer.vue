<template>
  <Teleport to="body">
    <Transition name="drawer-panel">
      <div
        v-if="open && request"
        class="fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[560px] flex-col border-l border-[var(--app-line)] bg-[var(--app-surface)] pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assistant-request-title"
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
            <UIcon :name="typeIcon" class="h-4 w-4 text-[var(--app-ink-soft)]" />
          </div>
          <div class="min-w-0 flex-1">
            <h2
              id="assistant-request-title"
              class="truncate text-base leading-tight font-semibold text-[var(--app-ink)]"
            >
              {{ request.name }}
            </h2>
            <p class="text-muted mt-0.5 truncate text-sm">
              {{ REQUEST_TYPE_LABELS[request.type] }} · {{ request.business_name }} ·
              {{ formatShortMonthDayTime(request.created_at) }}
            </p>
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
          <div class="flex flex-wrap items-center gap-1.5">
            <span class="app-badge" :class="request.type === 'urgent' ? 'app-badge--danger' : ''">
              {{ REQUEST_TYPE_LABELS[request.type] }}
            </span>
            <span class="app-badge" :class="statusBadgeClass">{{ REQUEST_STATUS_LABELS[request.status] }}</span>
            <span v-if="request.received_outside_hours" class="app-badge">
              <UIcon name="i-lucide-moon" class="h-3 w-3" />
              Hors horaires
            </span>
            <span v-if="request.is_test" class="app-badge" title="Laissée pendant une visite de test de l'opérateur">
              Test
            </span>
          </div>

          <section class="flex flex-col gap-2">
            <h3 class="app-label !text-[0.6rem]">Coordonnées</h3>
            <p class="text-sm text-[var(--app-ink)]">{{ request.name }}</p>
            <a
              v-if="contactLink"
              :href="contactLink"
              class="text-sm break-all text-[var(--app-ink)] underline underline-offset-2 hover:text-[var(--app-ink-soft)]"
            >
              {{ request.contact }}
            </a>
            <p v-else class="text-sm break-all text-[var(--app-ink)]">{{ request.contact }}</p>
            <p v-if="request.language" class="text-muted text-xs">
              Langue du visiteur : {{ request.language.toUpperCase() }}
            </p>
          </section>

          <section class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-4">
            <h3 class="app-label !text-[0.6rem]">Besoin</h3>
            <p class="text-sm leading-relaxed text-[var(--app-ink)]">
              {{ request.need_summary || request.need || 'Demande de rappel, sans détail.' }}
            </p>
            <p
              v-if="request.need_summary && request.need && request.need !== request.need_summary"
              class="text-muted text-xs leading-relaxed"
            >
              Mots du visiteur : « {{ request.need }} »
            </p>
            <p
              v-if="request.appointment_booked"
              class="flex items-start gap-1.5 text-sm leading-relaxed text-[var(--app-ink)]"
            >
              <UIcon name="i-lucide-calendar-check" class="mt-0.5 h-4 w-4 shrink-0" />
              <span>Rendez-vous réservé dans l'agenda du client : {{ request.appointment_booked }}</span>
            </p>
            <p
              v-else-if="request.appointment_slots.length > 0"
              class="flex items-start gap-1.5 text-sm leading-relaxed text-[var(--app-ink)]"
            >
              <UIcon name="i-lucide-calendar-days" class="mt-0.5 h-4 w-4 shrink-0" />
              <span>Créneaux souhaités (à confirmer) : {{ request.appointment_slots.join(' ou ') }}</span>
            </p>
          </section>

          <section
            v-if="request.photo_urls.length > 0"
            class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-4"
          >
            <h3 class="app-label !text-[0.6rem]">Photos ({{ request.photo_urls.length }})</h3>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="(url, index) in request.photo_urls"
                :key="url"
                type="button"
                class="block h-20 w-20 cursor-pointer overflow-hidden rounded-md border border-[var(--app-line)] transition-opacity hover:opacity-90"
                :aria-label="`Agrandir la photo ${index + 1}`"
                @click="lightboxIndex = index"
              >
                <img :src="url" alt="" loading="lazy" class="h-full w-full object-cover" />
              </button>
            </div>
          </section>

          <section class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-4">
            <h3 class="app-label !text-[0.6rem]">Conversation</h3>
            <p v-if="isLoadingTranscript" class="text-muted text-sm">Chargement…</p>
            <p v-else-if="transcript.length === 0" class="text-muted text-sm">
              Le visiteur a laissé ses coordonnées sans écrire à l'assistant.
            </p>
            <ol v-else class="flex flex-col gap-2">
              <li
                v-for="(line, index) in transcript"
                :key="index"
                class="max-w-[88%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed whitespace-pre-wrap"
                :class="
                  line.role === 'user'
                    ? 'self-end bg-[var(--app-ink)] text-[var(--app-bg)]'
                    : 'self-start border border-[var(--app-line)] bg-[var(--app-surface-2)] text-[var(--app-ink)]'
                "
              >
                {{ line.content }}
              </li>
            </ol>
          </section>

          <section class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-4">
            <label class="flex flex-col gap-1">
              <span class="app-label !text-[0.6rem]">Note interne</span>
              <textarea
                v-model="note"
                class="app-input min-h-20 resize-y"
                maxlength="2000"
                placeholder="Rappelé le 26/09, devis envoyé…"
              />
            </label>
            <button
              type="button"
              class="btn-secondary h-8 self-start text-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSaving || note.trim() === (request.owner_note ?? '')"
              @click="saveNote"
            >
              <UIcon v-if="isSaving" name="i-lucide-loader-circle" class="mr-1 h-3.5 w-3.5 animate-spin" />
              Enregistrer la note
            </button>
          </section>
        </div>

        <div class="flex flex-wrap items-center gap-2 border-t border-[var(--app-line)] px-5 py-4">
          <template v-if="request.status === 'new'">
            <button
              type="button"
              class="btn-primary h-9 text-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSaving"
              @click="setStatus('handled')"
            >
              <UIcon name="i-lucide-check" class="mr-1 h-3.5 w-3.5" />
              Marquer traitée
            </button>
            <button
              type="button"
              class="btn-secondary h-9 text-xs disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="isSaving"
              @click="setStatus('dropped')"
            >
              Sans suite
            </button>
          </template>
          <button
            v-else
            type="button"
            class="btn-secondary h-9 text-xs disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isSaving"
            @click="setStatus('new')"
          >
            <UIcon name="i-lucide-rotate-ccw" class="mr-1 h-3.5 w-3.5" />
            Rouvrir
          </button>
          <button
            v-if="request.prospect_id !== null"
            type="button"
            class="btn-secondary ml-auto h-9 text-xs"
            @click="openProspect"
          >
            <UIcon name="i-lucide-arrow-up-right" class="mr-1 h-3.5 w-3.5" />
            Prospect
          </button>
        </div>
      </div>
    </Transition>

    <UiImageLightbox
      v-if="open && request && request.photo_urls.length > 0"
      v-model="lightboxIndex"
      :photos="request.photo_urls"
    />
  </Teleport>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type {
  AiAssistantRequestDetail,
  AiAssistantRequestItem,
  AiAssistantRequestStatus,
  AiAssistantTranscriptLine,
} from '~/types/AiAssistant'
import type { Prospect } from '~/types'
import type { UseToastReturn } from '~/types/Composables'
import type { UiAssistantRequestDrawerEmits, UiAssistantRequestDrawerProps } from '~/types/UiAssistantRequestDrawer'
import { AiAssistantService } from '~/services/aiAssistantService'
import { ProspectsService } from '~/services/prospectsService'
import { useToast } from '~/composables/useToast'
import { useDrawerStackStore } from '~/stores/drawerStack'
import { contactHref } from '~/utils/contactLink'
import { formatShortMonthDayTime } from '~/utils/date'
import { REQUEST_STATUS_LABELS, REQUEST_TYPE_LABELS } from '~/utils/aiAssistantLabels'

const props: UiAssistantRequestDrawerProps = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  request: {
    type: Object as PropType<AiAssistantRequestItem | null>,
    default: null,
  },
  showBack: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<UiAssistantRequestDrawerEmits> = defineEmits<UiAssistantRequestDrawerEmits>()

const toast: UseToastReturn = useToast()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()

/** Icon of each request type, in the drawer header. */
const TYPE_ICONS: Record<string, string> = {
  question: 'i-lucide-message-circle-question',
  quote: 'i-lucide-receipt-text',
  appointment: 'i-lucide-calendar-days',
  urgent: 'i-lucide-siren',
  other: 'i-lucide-inbox',
}

const transcript: Ref<AiAssistantTranscriptLine[]> = ref([])
const loadingRequestId: Ref<number | null> = ref(null)
const isSaving: Ref<boolean> = ref(false)
const note: Ref<string> = ref('')
/** Index of the photo shown full screen, null when the lightbox is closed. */
const lightboxIndex: Ref<number | null> = ref(null)

const isLoadingTranscript: ComputedRef<boolean> = computed((): boolean => loadingRequestId.value !== null)

const typeIcon: ComputedRef<string> = computed(
  (): string => TYPE_ICONS[props.request?.type ?? 'other'] ?? 'i-lucide-inbox',
)

const statusBadgeClass: ComputedRef<string> = computed((): string => {
  if (props.request?.status === 'handled') return 'app-badge--success'
  if (props.request?.status === 'new') return 'app-badge--strong'
  return ''
})

const contactLink: ComputedRef<string | null> = computed((): string | null =>
  props.request ? contactHref(props.request.contact) : null,
)

/**
 * Whether a reply still belongs to the drawer on screen: not closed, not switched to another request meanwhile.
 * @param requestId - The request the call was made for.
 * @returns True when the reply may update the drawer.
 */
function isShowing(requestId: number): boolean {
  return props.open && props.request?.id === requestId
}

/**
 * Load the conversation the request came out of.
 * @param requestId - The request.
 * @returns A promise resolved once loaded.
 */
async function loadTranscript(requestId: number): Promise<void> {
  loadingRequestId.value = requestId
  try {
    const detail: AiAssistantRequestDetail = await AiAssistantService.getRequest(requestId)
    if (isShowing(requestId)) transcript.value = detail.transcript
  } catch {
    if (isShowing(requestId)) transcript.value = []
  } finally {
    if (loadingRequestId.value === requestId) loadingRequestId.value = null
  }
}

/**
 * Move the request to another status.
 * @param status - Its new status.
 * @returns A promise resolved once saved.
 */
async function setStatus(status: AiAssistantRequestStatus): Promise<void> {
  if (!props.request || isSaving.value) return
  const requestId: number = props.request.id
  isSaving.value = true
  try {
    const updated: AiAssistantRequestItem = await AiAssistantService.updateRequest(requestId, { status })
    // Broadcast even if the drawer moved on: the pages match the request by id.
    emit('updated', updated)
  } catch {
    toast.error('Mise à jour de la demande impossible.')
  } finally {
    isSaving.value = false
  }
}

/**
 * Save the owner's note on the request.
 * @returns A promise resolved once saved.
 */
async function saveNote(): Promise<void> {
  if (!props.request || isSaving.value) return
  const requestId: number = props.request.id
  isSaving.value = true
  try {
    const updated: AiAssistantRequestItem = await AiAssistantService.updateRequest(requestId, {
      owner_note: note.value.trim(),
    })
    emit('updated', updated)
    if (isShowing(requestId)) toast.success('Note enregistrée.')
  } catch {
    toast.error('Enregistrement de la note impossible.')
  } finally {
    isSaving.value = false
  }
}

/**
 * Open the request's prospect in the shared drawer, to act on it (call, add to a campaign…).
 * @returns A promise resolved once the prospect drawer is pushed.
 */
async function openProspect(): Promise<void> {
  if (!props.request || props.request.prospect_id === null) return
  try {
    const prospect: Prospect = await ProspectsService.getProspect(props.request.prospect_id)
    drawerStack.push({ kind: 'prospect', prospect })
  } catch {
    toast.error('Prospect introuvable.')
  }
}

watch(
  (): number | null => (props.open && props.request ? props.request.id : null),
  (requestId: number | null): void => {
    transcript.value = []
    lightboxIndex.value = null
    isSaving.value = false
    note.value = props.request?.owner_note ?? ''
    if (requestId !== null) void loadTranscript(requestId)
  },
  { immediate: true },
)

// The note follows the request when a page refreshes it (a status change elsewhere), without a reload.
watch(
  (): string | null => props.request?.owner_note ?? null,
  (ownerNote: string | null): void => {
    if (!isSaving.value) note.value = ownerNote ?? ''
  },
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
