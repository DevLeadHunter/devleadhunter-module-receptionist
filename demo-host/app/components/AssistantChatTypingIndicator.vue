<template>
  <div class="ai-typing" :aria-label="UI_LABELS[props.lang].typing"><i /><i /><i /></div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantChatTypingIndicatorProps } from '~/types/AssistantChatTypingIndicator'
import { UI_LABELS } from '~/constants/AssistantWidgetLabels'

const props: AssistantChatTypingIndicatorProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
})
</script>

<style scoped>
.ai-typing {
  align-self: flex-start;
  margin-left: 30px;
  display: flex;
  gap: 4px;
  padding: 13px 15px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line-soft);
  border-radius: 16px;
  border-bottom-left-radius: 5px;
  animation: ai-typing-in 0.18s ease-out both;
}
@keyframes ai-typing-in {
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
  .ai-typing {
    animation: none;
  }
}
.ai-typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ai-ink-dim);
  animation: ai-blink 1.1s infinite;
}
.ai-typing i:nth-child(2) {
  animation-delay: 0.18s;
}
.ai-typing i:nth-child(3) {
  animation-delay: 0.36s;
}
@keyframes ai-blink {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 0.9;
    transform: translateY(-3px);
  }
}
@media (prefers-reduced-motion: reduce) {
  .ai-typing i {
    animation: none;
  }
}
</style>
