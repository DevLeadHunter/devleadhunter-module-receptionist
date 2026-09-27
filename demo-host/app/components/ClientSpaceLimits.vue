<template>
  <form class="cs-limits" @submit.prevent="submit">
    <p class="cs-sec">Ce que {{ props.assistantName }} répond</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        {{ props.assistantName }} n’invente jamais de prix, de date ni d’engagement. Quand l’information n’est ni sur
        votre site ni sur votre fiche, la phrase ci-dessous est donnée. Réécrivez-la avec vos mots, vos vrais tarifs par
        exemple : elle sera alors toujours dite ainsi. Éteignez un sujet qui ne vous concerne pas.
      </p>
    </div>

    <fieldset class="cs-limits__fields" :disabled="props.isSaving || props.readOnly">
      <template v-for="draft in drafts" :key="draft.key">
        <p class="cs-sec">{{ draft.topic }}</p>
        <div class="cs-block cs-limits__block">
          <label class="cs-limits__switch">
            <span>Sujet actif</span>
            <input v-model="draft.enabled" type="checkbox" />
          </label>
          <label class="cs-field">
            <span class="cs-label">Sa phrase</span>
            <textarea
              v-model="draft.answer"
              class="cs-input cs-limits__answer"
              rows="3"
              :maxlength="MAX_ANSWER_CHARS"
              :disabled="!draft.enabled"
              :aria-label="`Réponse : ${draft.topic}`"
            ></textarea>
            <span class="cs-hint">{{ draft.answer.length }} / {{ MAX_ANSWER_CHARS }} · vide = la phrase proposée</span>
          </label>
        </div>
      </template>
    </fieldset>

    <div v-if="!props.readOnly" class="cs-limits__foot">
      <ClientSpaceSaveBar
        :is-busy="props.isSaving"
        :can-save="hasChanges"
        :error-message="props.errorMessage"
        :show-saved="props.hasSaved && !hasChanges"
      />
    </div>
  </form>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AiAssistantClientLimit, AiAssistantClientLimitUpdate } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceLimitsEmits, ClientSpaceLimitsProps } from '~/types/ClientSpaceLimits'

/** The longest answer the API keeps. */
const MAX_ANSWER_CHARS: number = 300

/**
 * The subjects the receptionist never improvises on (prices, delays, warranties…), each with the sentence the business
 * wants said, editable, and a switch to drop a subject.
 * @param limits The subjects as the API serves them.
 * @param assistantName The receptionist's first name.
 * @param isSaving A save is in flight.
 * @param errorMessage Why the last save was refused, if it was.
 * @param hasSaved The last save went through.
 * @param readOnly The example space: shown, never saved.
 */
const props: ClientSpaceLimitsProps = defineProps({
  limits: { type: Array as PropType<AiAssistantClientLimit[]>, required: true },
  assistantName: { type: String, required: true },
  isSaving: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  hasSaved: { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceLimitsEmits> = defineEmits<ClientSpaceLimitsEmits>()

const drafts: Ref<AiAssistantClientLimit[]> = ref(copyOf(props.limits))

const hasChanges: ComputedRef<boolean> = computed((): boolean =>
  drafts.value.some((draft: AiAssistantClientLimit, index: number): boolean => {
    const saved: AiAssistantClientLimit | undefined = props.limits[index]
    return saved === undefined || draft.enabled !== saved.enabled || draft.answer.trim() !== saved.answer
  }),
)

/**
 * A working copy of the limits, so typing never touches what the API served.
 * @param limits The limits.
 * @returns Their copy.
 */
function copyOf(limits: AiAssistantClientLimit[]): AiAssistantClientLimit[] {
  return limits.map((limit: AiAssistantClientLimit): AiAssistantClientLimit => ({ ...limit }))
}

/** Send every subject: the API keeps the edits and falls back to its default for an emptied sentence. */
function submit(): void {
  if (!hasChanges.value) return
  emit(
    'save',
    drafts.value.map((draft: AiAssistantClientLimit): AiAssistantClientLimitUpdate => ({
      key: draft.key,
      answer: draft.answer.trim(),
      enabled: draft.enabled,
    })),
  )
}

watch(
  (): AiAssistantClientLimit[] => props.limits,
  (saved: AiAssistantClientLimit[]): void => {
    drafts.value = copyOf(saved)
  },
)
</script>

<style scoped>
.cs-limits {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.cs-limits__fields {
  display: grid;
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}

.cs-limits__block {
  display: grid;
  gap: 12px;
  padding: 14px 16px 16px;
}

.cs-limits__switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 15px;
  font-weight: 600;
}

.cs-limits__switch input {
  width: 22px;
  height: 22px;
  accent-color: var(--cs-accent-strong);
}

.cs-limits__answer {
  resize: vertical;
  min-height: 84px;
  line-height: 1.45;
}

.cs-limits__foot {
  padding: 4px 0 24px;
}
</style>
