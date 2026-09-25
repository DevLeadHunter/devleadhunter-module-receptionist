<template>
  <div class="ai-chips">
    <button v-if="props.canSendPhoto" type="button" class="ai-chip" @click="emit('photo')">
      <AssistantIcon name="camera" class="ai-chip__icon" />
      {{ PHOTO_LABELS[props.lang].chip }}
    </button>
    <button type="button" class="ai-chip" @click="emit('appointment')">
      <AssistantIcon name="calendar" class="ai-chip__icon" />
      {{ APPOINTMENT_LABELS[props.lang].chip }}
    </button>
    <button
      v-for="suggestion in props.suggestions"
      :key="suggestion"
      type="button"
      class="ai-chip"
      @click="emit('suggest', suggestion)"
    >
      {{ suggestion }}
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantChatQuickRepliesEmits, AssistantChatQuickRepliesProps } from '~/types/AssistantChatQuickReplies'
import { APPOINTMENT_LABELS, PHOTO_LABELS } from '~/constants/AssistantWidgetLabels'

const props: AssistantChatQuickRepliesProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
  suggestions: {
    type: Array as PropType<string[]>,
    required: true,
  },
  canSendPhoto: {
    type: Boolean,
    default: true,
  },
})

const emit: EmitFn<AssistantChatQuickRepliesEmits> = defineEmits<AssistantChatQuickRepliesEmits>()
</script>

<style scoped>
.ai-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-self: flex-start;
  max-width: 94%;
  padding-left: 30px;
  /* The chips follow the greeting in, a beat later. */
  animation: ai-chips-in 0.2s ease-out 0.12s both;
}
@keyframes ai-chips-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ai-chips {
    animation: none;
  }
}
.ai-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid var(--ai-line);
  background: var(--ai-card);
  color: var(--ai-ink);
  font: inherit;
  font-size: 0.8rem;
  font-weight: 500;
  line-height: 1.3;
  padding: 8px 13px;
  border-radius: 999px;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.12s ease,
    border-color 0.12s ease;
}
.ai-chip:hover {
  border-color: var(--ai-ink);
  background: var(--ai-paper);
}
.ai-chip__icon {
  font-size: 14px;
  color: var(--ai-accent-text);
}
</style>
