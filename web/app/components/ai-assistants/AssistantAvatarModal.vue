<template>
  <Teleport to="body">
    <div
      v-if="props.open"
      class="fixed inset-0 z-[100] flex items-center justify-center backdrop-blur-sm"
      :style="{ backgroundColor: 'var(--app-overlay, rgba(0, 0, 0, 0.7))' }"
      @click.self="close"
    >
      <div
        class="app-card mx-4 w-full max-w-md p-6 shadow-[var(--app-shadow-soft)]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assistant-avatar-modal-title"
      >
        <h2 id="assistant-avatar-modal-title" class="font-display text-lg font-semibold text-[var(--app-ink)]">
          Votre image
        </h2>
        <p class="mt-1 text-sm leading-relaxed text-[var(--app-ink-soft)]">
          Une photo ou le logo du commerce, à la place du visage de {{ props.assistant.assistant_name }}.
        </p>

        <div class="mt-5 flex items-center gap-4">
          <AssistantPortrait
            v-if="props.assistant.avatar_url"
            :url="props.assistant.avatar_url"
            :name="props.assistant.assistant_name"
            :accent-color="props.accentColor"
            :background="previewBackground"
            size-class="h-24 w-24 text-2xl"
          />
          <span
            v-else
            class="flex h-24 w-24 shrink-0 items-center justify-center rounded-full border border-dashed border-[var(--app-ink-soft)] text-[var(--app-ink-soft)]"
          >
            <UIcon name="i-lucide-image-plus" class="h-7 w-7" />
          </span>
          <div class="flex min-w-0 flex-col items-start gap-2">
            <button
              ref="fileButton"
              type="button"
              class="app-btn-secondary h-9 px-3 text-sm disabled:opacity-50"
              :disabled="isBusy"
              @click="openFilePicker"
            >
              <UIcon
                :name="isUploading ? 'i-lucide-loader-circle' : 'i-lucide-upload'"
                :class="['h-4 w-4', isUploading && 'animate-spin']"
              />
              {{ props.assistant.avatar_url ? "Remplacer l'image" : 'Choisir une image' }}
            </button>
            <span class="text-xs leading-snug text-[var(--app-ink-soft)]">
              PNG, JPG ou WebP, 2 Mo maximum. Un PNG détouré garde un fond de couleur.
            </span>
          </div>
        </div>

        <div v-if="isCutOut" class="mt-5 flex flex-col gap-1">
          <div class="flex items-center justify-between gap-3">
            <span class="text-xs font-medium text-[var(--app-ink)]">Fond du portrait</span>
            <div class="flex items-center gap-2">
              <label
                class="relative h-8 w-10 shrink-0 cursor-pointer overflow-hidden rounded border border-[var(--app-line)]"
                :style="{ background: swatchBackground }"
              >
                <input
                  v-model="backgroundDraft"
                  type="color"
                  class="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  aria-label="Choisir la couleur de fond du portrait"
                />
              </label>
              <input
                v-model="backgroundDraft"
                type="text"
                class="app-input w-28"
                maxlength="7"
                placeholder="Automatique"
                aria-label="Couleur de fond du portrait en hexadécimal"
              />
              <button
                v-if="backgroundDraft"
                type="button"
                class="app-btn-secondary h-8 w-8 justify-center p-0"
                title="Revenir à la teinte automatique"
                aria-label="Revenir à la teinte automatique"
                @click="backgroundDraft = ''"
              >
                <UIcon name="i-lucide-rotate-ccw" class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <span class="text-[11px] text-[var(--app-ink-soft)]">
            {{
              previewBackground
                ? 'Le disque derrière le logo détouré.'
                : "Automatique : la teinte de la couleur d'accent."
            }}
          </span>
        </div>

        <p v-if="errorMessage" class="mt-4 text-sm text-[var(--app-red)]">{{ errorMessage }}</p>

        <div class="mt-6 flex flex-wrap items-center justify-between gap-3">
          <button
            v-if="props.assistant.avatar_url"
            type="button"
            class="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--app-ink-soft)] transition-colors hover:text-[var(--app-red)] disabled:opacity-50"
            :disabled="isBusy"
            @click="removeImage"
          >
            <UIcon
              :name="isRemoving ? 'i-lucide-loader-circle' : 'i-lucide-trash-2'"
              :class="['h-3.5 w-3.5', isRemoving && 'animate-spin']"
            />
            Supprimer l'image
          </button>
          <div class="ml-auto flex gap-2">
            <button type="button" class="app-btn-secondary" :disabled="isBusy" @click="close">Annuler</button>
            <button
              type="button"
              class="app-btn-primary disabled:opacity-50"
              :disabled="!props.assistant.avatar_url || isBusy"
              @click="useImage"
            >
              <UIcon v-if="isSaving" name="i-lucide-loader-circle" class="h-4 w-4 animate-spin" />
              {{ props.assistant.avatar_enabled ? 'Enregistrer' : 'Utiliser cette image' }}
            </button>
          </div>
        </div>

        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          class="hidden"
          @change="uploadPickedImage"
        />
      </div>
    </div>
  </Teleport>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import type { AiAssistantSummary } from '~/types/AiAssistant'
import type { AssistantAvatarModalEmits, AssistantAvatarModalProps } from '~/types/AssistantAvatarModal'
import type { UseToastReturn } from '~/types/Composables'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AssistantPortrait from '~/components/ai-assistants/AssistantPortrait.vue'
import { useToast } from '~/composables/useToast'
import { AiAssistantService } from '~/services/aiAssistantService'
import { portraitDiscBackground } from '~/utils/assistantPortrait'

/** The largest image the API takes, checked here first so a heavy photo is refused without waiting for the upload. */
const MAX_IMAGE_BYTES: number = 2 * 1024 * 1024

/** Starts of the API refusals worth showing as they are when the image is chosen. */
const CHOICE_REFUSALS: string[] = ['Couleur de fond', 'Image manquante']

const props: AssistantAvatarModalProps = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  assistant: {
    type: Object as PropType<AiAssistantSummary>,
    required: true,
  },
  accentColor: {
    type: String as PropType<string | null>,
    default: null,
  },
})

const emit: EmitFn<AssistantAvatarModalEmits> = defineEmits<AssistantAvatarModalEmits>()

const toast: UseToastReturn = useToast()

const fileInput: Ref<HTMLInputElement | null> = ref(null)
const fileButton: Ref<HTMLButtonElement | null> = ref(null)
const backgroundDraft: Ref<string> = ref('')
const isUploading: Ref<boolean> = ref(false)
const isRemoving: Ref<boolean> = ref(false)
const isSaving: Ref<boolean> = ref(false)
const errorMessage: Ref<string> = ref('')

const isBusy: ComputedRef<boolean> = computed((): boolean => isUploading.value || isRemoving.value || isSaving.value)

/** A cut-out image shows the disc around it, so its colour can be picked; a photo covers it. */
const isCutOut: ComputedRef<boolean> = computed(
  (): boolean => Boolean(props.assistant.avatar_url) && props.assistant.avatar_is_transparent,
)

const previewBackground: ComputedRef<string | null> = computed((): string | null =>
  isCutOut.value ? backgroundDraft.value.trim() || null : null,
)

/** What the colour swatch shows: the picked colour, else the accent's tint the disc takes automatically. */
const swatchBackground: ComputedRef<string> = computed(
  (): string => previewBackground.value || portraitDiscBackground(props.accentColor),
)

/** Close the dialog, unless a request is on its way. */
function close(): void {
  if (!isBusy.value) emit('close')
}

/**
 * Close on Escape, as the overlay does on a click.
 * @param event - The key pressed anywhere on the page.
 */
function closeOnEscape(event: KeyboardEvent): void {
  if (props.open && event.key === 'Escape') close()
}

/** Open the hidden file input. */
function openFilePicker(): void {
  fileInput.value?.click()
}

/**
 * Send the picked image; it replaces the previous one at once, and shows once chosen.
 * @param event - Native change event of the file input.
 * @returns A promise resolved once the API answered.
 */
async function uploadPickedImage(event: Event): Promise<void> {
  const input: HTMLInputElement | null = event.target as HTMLInputElement | null
  const file: File | null = input?.files?.[0] ?? null
  if (input) input.value = ''
  if (!file) return
  errorMessage.value = ''
  if (file.size > MAX_IMAGE_BYTES) {
    errorMessage.value = "L'image dépasse 2 Mo : réduisez-la ou choisissez-en une autre."
    return
  }
  isUploading.value = true
  try {
    emit('updated', await AiAssistantService.uploadAvatar(props.assistant.id, file))
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : "L'image n'a pas pu être envoyée."
  } finally {
    isUploading.value = false
  }
}

/**
 * Make the image the receptionist's portrait, on the disc colour picked.
 * @returns A promise resolved once the API answered.
 */
async function useImage(): Promise<void> {
  errorMessage.value = ''
  isSaving.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.update(props.assistant.id, {
      avatar_enabled: true,
      avatar_background: backgroundDraft.value.trim(),
    })
    emit('updated', updated)
    toast.success(`${updated.assistant_name} affiche maintenant votre image.`)
    emit('close')
  } catch (error: unknown) {
    const detail: string = error instanceof Error ? error.message : ''
    const isExplained: boolean = CHOICE_REFUSALS.some((prefix: string): boolean => detail.startsWith(prefix))
    errorMessage.value = isExplained ? detail : "L'image n'a pas pu être choisie pour le moment."
  } finally {
    isSaving.value = false
  }
}

/**
 * Delete the image: the receptionist shows its casting face again.
 * @returns A promise resolved once the API answered.
 */
async function removeImage(): Promise<void> {
  errorMessage.value = ''
  isRemoving.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.clearAvatar(props.assistant.id)
    emit('updated', updated)
    toast.success(
      props.assistant.avatar_enabled ? `${updated.assistant_name} retrouve son visage.` : 'Image supprimée.',
    )
  } catch (error: unknown) {
    errorMessage.value = error instanceof Error ? error.message : "L'image n'a pas pu être supprimée."
  } finally {
    isRemoving.value = false
  }
}

watch(
  (): boolean => props.open,
  async (isOpen: boolean): Promise<void> => {
    if (!isOpen) return
    backgroundDraft.value = props.assistant.avatar_background ?? ''
    errorMessage.value = ''
    await nextTick()
    fileButton.value?.focus()
  },
)

onMounted((): void => {
  window.addEventListener('keydown', closeOnEscape)
})

onBeforeUnmount((): void => {
  window.removeEventListener('keydown', closeOnEscape)
})
</script>
