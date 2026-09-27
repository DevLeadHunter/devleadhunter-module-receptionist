<template>
  <article class="cs-detail">
    <header v-if="props.showBack" class="cs-bar">
      <button type="button" class="cs-bar__back" @click="emit('back')">
        <ClientSpaceIcon name="chevron-left" />Demandes
      </button>
    </header>

    <form class="cs-detail__body" @submit.prevent="submit">
      <div class="cs-head">
        <span class="cs-avatar cs-avatar--lg cs-avatar--portrait">
          <AssistantAvatar
            :url="props.portraitUrl"
            :fallback-url="props.portraitFallbackUrl"
            :alt="props.assistantName"
          />
        </span>
        <div class="cs-head__text">
          <h1 class="cs-head__name">{{ props.assistantName }}</h1>
          <p class="cs-head__meta">{{ askedLabel }}</p>
        </div>
      </div>

      <p class="cs-sec">Sa question</p>
      <div class="cs-block">
        <p class="cs-question__quote">« {{ props.entry.question }} »</p>
        <p class="cs-text cs-text--dim">
          Je n’avais pas la réponse, j’ai proposé un rappel. Répondez comme au téléphone, je le dirai aux suivants.
        </p>
      </div>

      <p class="cs-sec">Votre réponse</p>
      <div class="cs-block">
        <textarea
          v-model="draft"
          class="cs-question__field"
          rows="4"
          maxlength="1000"
          placeholder="Par exemple : oui, sur demande, selon disponibilité."
          :disabled="props.isBusy || props.readOnly"
        />
      </div>

      <p v-if="props.errorMessage" class="cs-notice cs-notice--error cs-question__error">{{ props.errorMessage }}</p>

      <div v-if="!props.readOnly" class="cs-actions cs-actions--inline">
        <button type="submit" class="cs-btn cs-btn--primary" :disabled="!canSend">
          <ClientSpaceIcon name="send" />{{ props.isBusy ? 'Envoi…' : `Envoyer à ${props.assistantName}` }}
        </button>
        <button type="button" class="cs-quiet" :disabled="props.isBusy" @click="emit('dismiss')">
          Ne pas répondre à cette question
        </button>
      </div>
    </form>
  </article>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AiAssistantClientUnansweredEntry } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceQuestionEmits, ClientSpaceQuestionProps } from '~/types/ClientSpaceQuestion'

/**
 * One question the receptionist could not answer, asked the way an employee would: her question, a field for the
 * answer she will give from now on, a button.
 * @param entry The question, with how often visitors asked it.
 * @param assistantName The receptionist's first name.
 * @param portraitUrl Her photo.
 * @param portraitFallbackUrl The bust drawn when the photo is missing.
 * @param isBusy A call is in flight.
 * @param errorMessage Why the last call was refused, if it was.
 * @param readOnly The example space: shown, never answered.
 * @param showBack On a phone, the question replaces the list and shows a way back.
 */
const props: ClientSpaceQuestionProps = defineProps({
  entry: { type: Object as PropType<AiAssistantClientUnansweredEntry>, required: true },
  assistantName: { type: String, required: true },
  portraitUrl: { type: String, required: true },
  portraitFallbackUrl: { type: String, required: true },
  isBusy: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  readOnly: { type: Boolean, default: false },
  showBack: { type: Boolean, default: true },
})

const emit: EmitFn<ClientSpaceQuestionEmits> = defineEmits<ClientSpaceQuestionEmits>()

const draft: Ref<string> = ref('')

const askedLabel: ComputedRef<string> = computed((): string =>
  props.entry.count > 1 ? `Question posée ${props.entry.count} fois` : 'Question posée une fois',
)

const canSend: ComputedRef<boolean> = computed((): boolean => draft.value.trim().length > 0 && !props.isBusy)

/** Hand the answer over; the parent records it and closes the question. */
function submit(): void {
  if (!canSend.value) return
  emit('answer', draft.value.trim())
}

watch(
  (): string => props.entry.question,
  (): void => {
    draft.value = ''
  },
)
</script>

<style scoped>
.cs-detail {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.cs-detail__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding-bottom: 16px;
}

.cs-question__quote {
  margin: 0;
  padding: 14px 16px 4px;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.35;
}

.cs-question__field {
  display: block;
  width: 100%;
  box-sizing: border-box;
  min-height: 110px;
  padding: 12px 16px;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 15.5px;
  line-height: 1.5;
  color: var(--cs-ink);
  resize: vertical;
}

.cs-question__field:focus {
  outline: none;
  box-shadow: inset 0 0 0 2px var(--cs-accent);
}

.cs-question__error {
  padding: 12px 16px 0;
}

.cs-actions--inline {
  margin-top: auto;
}
</style>
