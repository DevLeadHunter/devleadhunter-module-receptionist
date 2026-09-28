<template>
  <template v-for="(part, partIndex) in props.parts" :key="partIndex">
    <a
      v-if="part.kind === 'link'"
      :href="part.value"
      target="_blank"
      rel="noopener noreferrer nofollow"
      class="ai-message-inline__link"
      >{{ part.value }}</a
    >
    <strong v-else-if="part.kind === 'bold'" class="ai-message-inline__bold">{{ part.value }}</strong>
    <br v-else-if="part.kind === 'break'" />
    <template v-else>{{ part.value }}</template>
  </template>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { AssistantMessagePart } from '~/types/AssistantMessage'
import type { AssistantChatMessageInlineProps } from '~/types/AssistantChatMessageInline'

const props: AssistantChatMessageInlineProps = defineProps({
  parts: {
    type: Array as PropType<AssistantMessagePart[]>,
    required: true,
  },
})
</script>

<style scoped>
.ai-message-inline__link {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
  overflow-wrap: anywhere;
}
.ai-message-inline__bold {
  font-weight: 600;
}
</style>
