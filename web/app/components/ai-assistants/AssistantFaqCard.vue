<template>
  <div class="card overflow-hidden p-0">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--app-line)] px-5 py-4">
      <div>
        <h2 class="font-semibold text-[var(--app-ink)]">Questions sans réponse</h2>
        <p class="text-xs text-[var(--app-ink-soft)]">
          Ce que les visiteurs ont demandé et que {{ props.assistantName }} ne savait pas. Répondez en une phrase : elle
          la reprend telle quelle.
        </p>
      </div>
      <span v-if="unanswered.length > 0" class="app-badge app-badge--strong">{{ unanswered.length }}</span>
    </div>

    <UiLoader v-if="isLoading" label="Chargement des questions…" />

    <p
      v-else-if="unanswered.length === 0 && faq.length === 0"
      class="px-5 py-8 text-center text-sm text-[var(--app-ink-soft)]"
    >
      Rien pour l'instant : {{ props.assistantName }} a su répondre à tout.
    </p>

    <template v-else>
      <ul v-if="unanswered.length > 0" class="divide-y divide-[var(--app-line-soft)]">
        <li v-for="(entry, index) in unanswered" :key="entry.question" class="space-y-2 px-5 py-3">
          <p class="text-sm font-medium text-[var(--app-ink)]">
            « {{ entry.question }} »
            <span v-if="entry.count > 1" class="ml-2 text-xs font-normal text-[var(--app-ink-soft)]">
              demandé {{ entry.count }} fois
            </span>
          </p>
          <template v-if="answeringIndex === index">
            <textarea
              v-model="answerDraft"
              class="app-input min-h-20 w-full resize-y"
              rows="3"
              maxlength="1000"
              placeholder="La réponse, comme le commerçant la dirait au téléphone"
              :disabled="isSaving"
            />
            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                class="btn-primary h-8 text-xs"
                :disabled="!answerDraft.trim() || isSaving"
                @click="saveAnswer(entry)"
              >
                {{ isSaving ? 'Enregistrement…' : 'Enregistrer la réponse' }}
              </button>
              <button type="button" class="btn-secondary h-8 text-xs" :disabled="isSaving" @click="closeAnswer">
                Annuler
              </button>
            </div>
          </template>
          <div v-else class="flex flex-wrap gap-2">
            <button type="button" class="btn-secondary h-8 text-xs" :disabled="isSaving" @click="openAnswer(index)">
              Répondre
            </button>
            <button
              type="button"
              class="h-8 cursor-pointer px-2 text-xs text-[var(--app-ink-soft)] underline underline-offset-4 hover:text-[var(--app-ink)]"
              :disabled="isSaving"
              @click="dismiss(index)"
            >
              Ignorer
            </button>
          </div>
        </li>
      </ul>

      <div v-if="faq.length > 0" class="border-t border-[var(--app-line)] px-5 py-4">
        <h3 class="app-label !text-[0.6rem]">Réponses en place ({{ faq.length }})</h3>
        <ul class="mt-3 divide-y divide-[var(--app-line-soft)]">
          <li v-for="(entry, index) in faq" :key="`${entry.question}-${entry.created_at}`" class="space-y-2 py-3">
            <template v-if="editingIndex === index">
              <input
                v-model="editQuestion"
                type="text"
                class="app-input w-full"
                maxlength="200"
                placeholder="La question"
                :disabled="isSaving"
              />
              <textarea
                v-model="editAnswer"
                class="app-input min-h-20 w-full resize-y"
                rows="3"
                maxlength="1000"
                placeholder="La réponse"
                :disabled="isSaving"
              />
              <div class="flex flex-wrap gap-2">
                <button
                  type="button"
                  class="btn-primary h-8 text-xs"
                  :disabled="!editQuestion.trim() || !editAnswer.trim() || isSaving"
                  @click="saveEdit(index)"
                >
                  Enregistrer
                </button>
                <button type="button" class="btn-secondary h-8 text-xs" :disabled="isSaving" @click="closeEdit">
                  Annuler
                </button>
              </div>
            </template>
            <template v-else>
              <p class="text-sm font-medium text-[var(--app-ink)]">{{ entry.question }}</p>
              <p class="text-sm text-[var(--app-ink-soft)]">{{ entry.answer }}</p>
              <div class="flex flex-wrap gap-2">
                <button type="button" class="btn-secondary h-8 text-xs" :disabled="isSaving" @click="openEdit(index)">
                  Modifier
                </button>
                <button
                  type="button"
                  class="h-8 cursor-pointer px-2 text-xs text-[var(--app-red)] underline underline-offset-4"
                  :disabled="isSaving"
                  @click="remove(index)"
                >
                  Supprimer
                </button>
              </div>
            </template>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { Ref } from 'vue'
import { onMounted, ref, watch } from 'vue'
import type { AiAssistantFaqEntry, AiAssistantFaqResponse, AiAssistantUnansweredEntry } from '~/types/AiAssistant'
import type { AssistantFaqCardProps } from '~/types/AssistantFaqCard'
import type { UseToastReturn } from '~/types/Composables'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useToast } from '~/composables/useToast'

/** What visitors asked without an answer, with a field to answer each, and the answers in place, editable. */
const props: AssistantFaqCardProps = defineProps({
  assistantId: {
    type: Number,
    required: true,
  },
  assistantName: {
    type: String,
    required: true,
  },
})

const toast: UseToastReturn = useToast()

const unanswered: Ref<AiAssistantUnansweredEntry[]> = ref([])
const faq: Ref<AiAssistantFaqEntry[]> = ref([])
const isLoading: Ref<boolean> = ref(true)
const isSaving: Ref<boolean> = ref(false)
/** The question being answered, as its position in the list; none when -1. */
const answeringIndex: Ref<number> = ref(-1)
const answerDraft: Ref<string> = ref('')
/** The answer being edited, as its position in the list; none when -1. */
const editingIndex: Ref<number> = ref(-1)
const editQuestion: Ref<string> = ref('')
const editAnswer: Ref<string> = ref('')

/**
 * Take the two lists as the API returned them.
 * @param response - The lists.
 */
function applyResponse(response: AiAssistantFaqResponse): void {
  unanswered.value = response.unanswered
  faq.value = response.faq
}

/**
 * Load the two lists of the assistant.
 * @returns A promise resolved once loaded.
 */
async function load(): Promise<void> {
  isLoading.value = true
  try {
    applyResponse(await AiAssistantService.getFaq(props.assistantId))
  } catch {
    toast.error('Les questions ne se chargent pas pour le moment.')
  } finally {
    isLoading.value = false
  }
}

/**
 * Open the answer field under a question.
 * @param index - The question's position.
 */
function openAnswer(index: number): void {
  answeringIndex.value = index
  answerDraft.value = ''
}

/** Close the answer field without recording anything. */
function closeAnswer(): void {
  answeringIndex.value = -1
  answerDraft.value = ''
}

/**
 * Record the answer to a question: it joins the answers in place and leaves the unanswered list.
 * @param entry - The question answered.
 * @returns A promise resolved once saved.
 */
async function saveAnswer(entry: AiAssistantUnansweredEntry): Promise<void> {
  const answer: string = answerDraft.value.trim()
  if (!answer || isSaving.value) return
  isSaving.value = true
  try {
    applyResponse(await AiAssistantService.addFaq(props.assistantId, { question: entry.question, answer }))
    closeAnswer()
    toast.success('Réponse enregistrée.')
  } catch {
    toast.error("La réponse n'a pas pu être enregistrée.")
  } finally {
    isSaving.value = false
  }
}

/**
 * Drop a question without answering it.
 * @param index - The question's position.
 * @returns A promise resolved once dropped.
 */
async function dismiss(index: number): Promise<void> {
  if (isSaving.value) return
  isSaving.value = true
  try {
    await AiAssistantService.dismissUnanswered(props.assistantId, index)
    unanswered.value = unanswered.value.filter(
      (_: AiAssistantUnansweredEntry, position: number): boolean => position !== index,
    )
    if (answeringIndex.value === index) closeAnswer()
  } catch {
    toast.error("La question n'a pas pu être retirée.")
  } finally {
    isSaving.value = false
  }
}

/**
 * Open an answer in place for editing.
 * @param index - The answer's position.
 */
function openEdit(index: number): void {
  const entry: AiAssistantFaqEntry | undefined = faq.value[index]
  if (!entry) return
  editingIndex.value = index
  editQuestion.value = entry.question
  editAnswer.value = entry.answer
}

/** Close the edit form without saving. */
function closeEdit(): void {
  editingIndex.value = -1
  editQuestion.value = ''
  editAnswer.value = ''
}

/**
 * Save an edited answer.
 * @param index - The answer's position.
 * @returns A promise resolved once saved.
 */
async function saveEdit(index: number): Promise<void> {
  const question: string = editQuestion.value.trim()
  const answer: string = editAnswer.value.trim()
  if (!question || !answer || isSaving.value) return
  isSaving.value = true
  try {
    applyResponse(await AiAssistantService.updateFaq(props.assistantId, index, { question, answer }))
    closeEdit()
  } catch {
    toast.error("La réponse n'a pas pu être modifiée.")
  } finally {
    isSaving.value = false
  }
}

/**
 * Delete an answer in place.
 * @param index - The answer's position.
 * @returns A promise resolved once deleted.
 */
async function remove(index: number): Promise<void> {
  if (isSaving.value) return
  isSaving.value = true
  try {
    await AiAssistantService.deleteFaq(props.assistantId, index)
    faq.value = faq.value.filter((_: AiAssistantFaqEntry, position: number): boolean => position !== index)
    if (editingIndex.value === index) closeEdit()
  } catch {
    toast.error("La réponse n'a pas pu être supprimée.")
  } finally {
    isSaving.value = false
  }
}

watch(
  (): number => props.assistantId,
  (): void => {
    load()
  },
)

onMounted((): void => {
  load()
})
</script>
