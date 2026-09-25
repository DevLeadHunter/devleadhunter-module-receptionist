<template>
  <form class="ai-compose" @submit.prevent="emit('send')">
    <button
      type="button"
      class="ai-compose__tool"
      :aria-label="PHOTO_LABELS[props.lang].button"
      :title="PHOTO_LABELS[props.lang].button"
      :disabled="props.isBusy || !props.canSendPhoto"
      @click="emit('photo')"
    >
      <AssistantIcon name="camera" />
    </button>
    <button
      type="button"
      class="ai-compose__tool"
      :aria-label="APPOINTMENT_LABELS[props.lang].button"
      :title="APPOINTMENT_LABELS[props.lang].button"
      :disabled="props.isBusy || !props.canBook"
      @click="emit('appointment')"
    >
      <AssistantIcon name="calendar" />
    </button>
    <textarea
      :value="props.modelValue"
      rows="1"
      maxlength="2000"
      :placeholder="UI_PLACEHOLDER[props.lang]"
      :aria-label="UI_LABELS[props.lang].message"
      @input="onInput"
      @keydown.enter.exact.prevent="emit('send')"
    />
    <button
      type="submit"
      class="ai-compose__send"
      :aria-label="UI_LABELS[props.lang].send"
      :disabled="props.isBusy || !props.modelValue.trim()"
    >
      <AssistantIcon name="send" />
    </button>
  </form>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantChatComposerEmits, AssistantChatComposerProps } from '~/types/AssistantChatComposer'
import { APPOINTMENT_LABELS, PHOTO_LABELS, UI_LABELS, UI_PLACEHOLDER } from '~/constants/AssistantWidgetLabels'

const props: AssistantChatComposerProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
  modelValue: {
    type: String,
    required: true,
  },
  isBusy: {
    type: Boolean,
    default: false,
  },
  canSendPhoto: {
    type: Boolean,
    default: true,
  },
  canBook: {
    type: Boolean,
    default: true,
  },
})

const emit: EmitFn<AssistantChatComposerEmits> = defineEmits<AssistantChatComposerEmits>()

/**
 * Report what the visitor types.
 * @param event - The textarea's input event.
 */
function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}
</script>

<style scoped>
.ai-compose {
  display: flex;
  gap: 8px;
  padding: 10px 12px 12px;
  border-top: 1px solid var(--ai-line-soft);
  background: var(--ai-card);
  align-items: flex-end;
}
.ai-compose textarea {
  flex: 1;
  min-width: 0;
  resize: none;
  border: 1px solid var(--ai-line);
  border-radius: 21px;
  padding: 10px 14px;
  font: inherit;
  /* 16px minimum: below it, iOS Safari zooms the whole page when the field is focused. */
  font-size: 16px;
  background: var(--ai-paper-2);
  color: var(--ai-ink);
  max-height: 96px;
  min-height: 42px;
  line-height: 1.35;
}
/* An empty field keeps its hint on one line, however narrow the bar is beside its tool buttons. */
.ai-compose textarea:placeholder-shown {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ai-compose textarea:focus {
  outline: 2px solid var(--ai-accent-strong);
  outline-offset: 1px;
}
.ai-compose__tool,
.ai-compose__send {
  flex: none;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 19px;
  cursor: pointer;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    color 0.12s ease;
}
.ai-compose__tool {
  border: 1px solid var(--ai-line);
  background: var(--ai-card);
  color: var(--ai-ink-dim);
}
.ai-compose__tool:hover {
  border-color: var(--ai-ink);
  color: var(--ai-ink);
}
.ai-compose__tool:disabled {
  opacity: 0.4;
  cursor: default;
}
.ai-compose__send {
  border: 0;
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
}
.ai-compose__send:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
