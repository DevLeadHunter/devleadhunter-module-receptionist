<template>
  <div class="ai-callback">
    <button type="button" class="ai-callback__btn" @click="emit('open')">
      <AssistantIcon name="pencil" class="ai-callback__icon" />
      {{ LEAD_LABELS[props.lang].open }}
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantChatCallbackBarEmits, AssistantChatCallbackBarProps } from '~/types/AssistantChatCallbackBar'
import { LEAD_LABELS } from '~/constants/AssistantWidgetLabels'

const props: AssistantChatCallbackBarProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
})

const emit: EmitFn<AssistantChatCallbackBarEmits> = defineEmits<AssistantChatCallbackBarEmits>()
</script>

<style scoped>
/* A quiet text link above the composer: the way out for whoever would rather be called back. */
.ai-callback {
  padding: 0 14px 6px;
  background: var(--ai-paper-2);
  text-align: center;
}
.ai-callback__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--ai-ink-dim);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 500;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: var(--ai-line);
  text-underline-offset: 3px;
  transition:
    color 0.12s ease,
    text-decoration-color 0.12s ease;
}
.ai-callback__btn:hover {
  color: var(--ai-ink);
  text-decoration-color: var(--ai-ink);
}
.ai-callback__icon {
  font-size: 13px;
}
</style>
