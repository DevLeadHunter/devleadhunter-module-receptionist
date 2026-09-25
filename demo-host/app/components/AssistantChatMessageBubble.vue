<template>
  <div class="ai-m" :class="[`ai-m--${props.message.role}`, { 'ai-m--with-portrait': props.avatarUrl !== null }]">
    <span v-if="props.avatarUrl !== null" class="ai-m__portrait" aria-hidden="true">
      <AssistantAvatar :url="props.avatarUrl" :fallback-url="props.avatarFallbackUrl" :alt="props.assistantName" />
    </span>
    <div class="ai-m__bubble" :class="{ 'ai-m__bubble--photo': props.photoPreviewUrl !== null }">
      <img
        v-if="props.photoPreviewUrl !== null"
        :src="props.photoPreviewUrl"
        :alt="props.message.content"
        class="ai-m__photo"
      />
      <template v-else-if="props.message.role === 'assistant'">
        <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
          <p v-if="block.kind === 'paragraph'" class="ai-m__p">
            <AssistantChatMessageInline :parts="block.parts" />
          </p>
          <ol v-else-if="block.ordered" class="ai-m__list">
            <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
              <AssistantChatMessageInline :parts="item" />
            </li>
          </ol>
          <ul v-else class="ai-m__list">
            <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
              <AssistantChatMessageInline :parts="item" />
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
.ai-m {
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
  .ai-m {
    animation: none;
  }
}
.ai-m--assistant {
  align-self: flex-start;
  /* Room for the portrait beside the last bubble of a run, so every bubble of the run lines up. */
  padding-left: 30px;
}
.ai-m--with-portrait {
  padding-left: 0;
}
.ai-m--user {
  align-self: flex-end;
}
.ai-m__portrait {
  width: 22px;
  height: 22px;
  flex: none;
  margin-bottom: 2px;
}
.ai-m__bubble {
  min-width: 0;
  padding: 10px 14px;
  font-size: 0.9rem;
  line-height: 1.5;
  word-wrap: break-word;
  border-radius: 16px;
}
.ai-m--assistant .ai-m__bubble {
  background: var(--ai-card);
  color: var(--ai-ink);
  border: 1px solid var(--ai-line-soft);
  border-bottom-left-radius: 5px;
}
.ai-m--user .ai-m__bubble {
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
  border-bottom-right-radius: 5px;
  /* The visitor's own line breaks are kept as typed. */
  white-space: pre-wrap;
}
.ai-m__bubble--photo {
  padding: 4px;
}
.ai-m__photo {
  display: block;
  max-width: 180px;
  max-height: 180px;
  border-radius: 12px;
  object-fit: cover;
}
/* Blocks of a laid-out reply: a beat between two paragraphs or a paragraph and its list. */
.ai-m__p,
.ai-m__list {
  margin: 0;
}
.ai-m__p + .ai-m__p,
.ai-m__p + .ai-m__list,
.ai-m__list + .ai-m__p,
.ai-m__list + .ai-m__list {
  margin-top: 8px;
}
.ai-m__list {
  padding-left: 1.2em;
}
.ai-m__list li + li {
  margin-top: 4px;
}
.ai-m__list li::marker {
  color: var(--ai-accent-text);
}
</style>
