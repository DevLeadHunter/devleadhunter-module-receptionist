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
.ai-callback {
  padding: 0 14px 8px;
  background: var(--ai-paper-2);
}
.ai-callback__btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px dashed var(--ai-line);
  background: transparent;
  color: var(--ai-ink-dim);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 500;
  padding: 7px 12px;
  border-radius: 999px;
  cursor: pointer;
}
.ai-callback__btn:hover {
  border-color: var(--ai-ink);
  color: var(--ai-ink);
}
.ai-callback__icon {
  font-size: 13px;
}
</style>
