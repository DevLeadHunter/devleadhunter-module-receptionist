<template>
  <div
    class="ai-message"
    :class="[`ai-message--${props.message.role}`, { 'ai-message--with-portrait': props.avatarUrl !== null }]"
  >
    <span v-if="props.avatarUrl !== null" class="ai-message__portrait" aria-hidden="true">
      <AssistantAvatar :url="props.avatarUrl" :fallback-url="props.avatarFallbackUrl" :alt="props.assistantName" />
    </span>
    <div class="ai-message__bubble" :class="{ 'ai-message__bubble--photo': props.photoPreviewUrl !== null }">
      <img
        v-if="props.photoPreviewUrl !== null"
        :src="props.photoPreviewUrl"
        :alt="props.message.content"
        class="ai-message__photo"
      />
      <template v-else-if="props.message.role === 'assistant'">
        <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
          <p v-if="block.kind === 'paragraph'" class="ai-message__paragraph">
            <AssistantChatMessageInline :parts="block.parts" />
          </p>
          <ol v-else-if="block.ordered" class="ai-message__list">
            <li v-for="(listItem, listItemIndex) in block.items" :key="listItemIndex" class="ai-message__list-item">
              <AssistantChatMessageInline :parts="listItem" />
            </li>
          </ol>
          <ul v-else class="ai-message__list">
            <li v-for="(listItem, listItemIndex) in block.items" :key="listItemIndex" class="ai-message__list-item">
              <AssistantChatMessageInline :parts="listItem" />
            </li>
          </ul>
        </template>
      </template>
      <template v-else>{{ props.message.content }}</template>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import type { AssistantChatMessage } from '~/types/AiAssistant'
import type { AssistantChatMessageBubbleProps } from '~/types/AssistantChatMessageBubble'
import type { AssistantMessageBlock } from '~/types/AssistantMessage'
import AssistantChatMessageInline from '~/components/AssistantChatMessageInline.vue'
import { MessageFormatUtils } from '~/utils/MessageFormatUtils'

const props: AssistantChatMessageBubbleProps = defineProps({
  message: {
    type: Object as PropType<AssistantChatMessage>,
    required: true,
  },
  photoPreviewUrl: {
    type: String as PropType<string | null>,
    default: null,
  },
  avatarUrl: {
    type: String as PropType<string | null>,
    default: null,
  },
  avatarFallbackUrl: {
    type: String,
    required: true,
  },
  assistantName: {
    type: String,
    required: true,
  },
})

/** The reply laid out: paragraphs and lists, re-read as the streamed text grows. */
const blocks: ComputedRef<AssistantMessageBlock[]> = computed((): AssistantMessageBlock[] =>
  MessageFormatUtils.blocks(props.message.content),
)
</script>

<style scoped>
.ai-message {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 88%;
  animation: ai-bubble-in 0.18s ease-out both;
}
@keyframes ai-bubble-in {
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
  .ai-message {
    animation: none;
  }
}
.ai-message--assistant {
  align-self: flex-start;
  /* Room for the portrait beside the last bubble of a run, so every bubble of the run lines up. */
  padding-left: 30px;
}
.ai-message--with-portrait {
  padding-left: 0;
}
.ai-message--user {
  align-self: flex-end;
}
.ai-message__portrait {
  width: 22px;
  height: 22px;
  flex: none;
  margin-bottom: 2px;
}
.ai-message__bubble {
  min-width: 0;
  padding: 10px 14px;
  font-size: 0.9rem;
  line-height: 1.5;
  word-wrap: break-word;
  border-radius: 16px;
}
.ai-message--assistant .ai-message__bubble {
  background: var(--ai-card);
  color: var(--ai-ink);
  border: 1px solid var(--ai-line-soft);
  border-bottom-left-radius: 5px;
}
.ai-message--user .ai-message__bubble {
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
  border-bottom-right-radius: 5px;
  /* The visitor's own line breaks are kept as typed. */
  white-space: pre-wrap;
}
.ai-message__bubble--photo {
  padding: 4px;
}
.ai-message__photo {
  display: block;
  max-width: 180px;
  max-height: 180px;
  border-radius: 12px;
  object-fit: cover;
}
.ai-message__paragraph,
.ai-message__list {
  margin: 0;
}
.ai-message__paragraph + .ai-message__paragraph,
.ai-message__paragraph + .ai-message__list,
.ai-message__list + .ai-message__paragraph,
.ai-message__list + .ai-message__list {
  margin-top: 8px;
}
.ai-message__list {
  padding-left: 1.2em;
}
.ai-message__list-item + .ai-message__list-item {
  margin-top: 4px;
}
.ai-message__list-item::marker {
  color: var(--ai-accent-text);
}
</style>
