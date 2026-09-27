<template>
  <div class="assistant-chat-window">
    <AssistantChat
      :config="props.assistant"
      inline
      @lead-sent="emit('lead-sent', $event)"
      @example-played="emit('example-played')"
    />
  </div>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantChatEmits } from '~/types/AssistantChat'
import type { AssistantChatWindowProps } from '~/types/AssistantChatWindow'

const props: AssistantChatWindowProps = defineProps({
  assistant: { type: Object as PropType<AiAssistantConfig>, required: true },
})

const emit: EmitFn<AssistantChatEmits> = defineEmits<AssistantChatEmits>()
</script>

<style scoped>
.assistant-chat-window {
  height: clamp(520px, 74vh, 640px);
  display: flex;
  flex-direction: column;
  border-radius: 22px;
  border: 1px solid var(--ia-line);
  background: var(--ia-card);
  box-shadow: 0 30px 70px -34px rgba(23, 19, 13, 0.45);
  overflow: hidden;
}
.assistant-chat-window :deep(.ai-widget--inline) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.assistant-chat-window :deep(.ai-panel--inline) {
  flex: 1;
  min-height: 0;
  height: auto;
}
@media (max-width: 640px) {
  .assistant-chat-window {
    height: min(560px, 78vh);
  }
}
</style>
