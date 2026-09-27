<template>
  <div class="cs-learned">
    <p class="cs-sec">{{ countLabel }}</p>
    <div class="cs-block">
      <dl v-if="props.faq.length > 0" class="cs-learned__list">
        <template v-for="entry in props.faq" :key="`${entry.question}-${entry.created_at}`">
          <dt class="cs-learned__question">{{ entry.question }}</dt>
          <dd class="cs-learned__answer">{{ entry.answer }}</dd>
        </template>
      </dl>
      <p v-else class="cs-text cs-text--dim">
        Dès qu’un visiteur pose une question à laquelle {{ props.assistantName }} ne sait pas répondre, elle vous la
        transmet dans vos demandes. Votre réponse apparaît ici, et elle la reprend telle quelle.
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientFaqEntry } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceLearnedAnswersProps } from '~/types/ClientSpaceLearnedAnswers'

/**
 * The answers the business gave its receptionist, which she now uses as they are.
 * @param faq The answers, newest first.
 * @param assistantName The receptionist's first name.
 */
const props: ClientSpaceLearnedAnswersProps = defineProps({
  faq: { type: Array as PropType<AiAssistantClientFaqEntry[]>, required: true },
  assistantName: { type: String, required: true },
})

const countLabel: ComputedRef<string> = computed((): string => {
  if (props.faq.length === 0) return 'Vos réponses'
  return props.faq.length === 1 ? '1 réponse apprise' : `${props.faq.length} réponses apprises`
})
</script>

<style scoped>
.cs-learned {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.cs-learned__list {
  margin: 0;
  display: grid;
}

.cs-learned__question {
  padding: 14px 16px 2px;
  font-size: 15.5px;
  font-weight: 600;
  line-height: 1.4;
}

.cs-learned__answer {
  margin: 0;
  padding: 0 16px 14px;
  font-size: 14.5px;
  line-height: 1.5;
  color: var(--cs-dim);
  border-bottom: 1px solid var(--cs-line);
}

.cs-learned__answer:last-child {
  border-bottom: 0;
}
</style>
