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
        <template v-for="(part, partIndex) in MessageLinkUtils.parts(props.message.content)" :key="partIndex">
          <a
            v-if="part.kind === 'link'"
            :href="part.value"
            target="_blank"
            rel="noopener noreferrer nofollow"
            class="ai-m__link"
            >{{ part.value }}</a
          >
          <template v-else>{{ part.value }}</template>
        </template>
      </template>
      <template v-else>{{ props.message.content }}</template>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { AssistantChatMessage } from '~/types/AiAssistant'
import type { AssistantChatMessageBubbleProps } from '~/types/AssistantChatMessageBubble'
import { MessageLinkUtils } from '~/utils/MessageLinkUtils'

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
  white-space: pre-wrap;
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
.ai-m__link {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
  overflow-wrap: anywhere;
}
</style>
