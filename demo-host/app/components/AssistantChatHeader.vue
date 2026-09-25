<template>
  <header class="ai-head">
    <span class="ai-head__portrait">
      <AssistantAvatar :url="props.avatarUrl" :fallback-url="props.avatarFallbackUrl" :alt="props.assistantName" />
      <i class="ai-head__dot" aria-hidden="true" />
    </span>
    <span class="ai-head__who">
      <b class="ai-head__name">{{ props.assistantName }}</b>
      <span class="ai-head__role">{{ props.roleLabel }} · {{ props.businessName }}</span>
    </span>
    <span class="ai-head__online">{{ props.onlineLabel }}</span>
    <button
      v-if="props.canClose"
      ref="closeButton"
      type="button"
      class="ai-head__close"
      aria-label="Fermer"
      @click="emit('close')"
    >
      <AssistantIcon name="close" />
    </button>
  </header>
</template>

<script lang="ts" setup>
import type { EmitFn, Ref } from 'vue'
import { ref } from 'vue'
import type { AssistantChatHeaderEmits, AssistantChatHeaderProps } from '~/types/AssistantChatHeader'

const props: AssistantChatHeaderProps = defineProps({
  assistantName: {
    type: String,
    required: true,
  },
  businessName: {
    type: String,
    required: true,
  },
  roleLabel: {
    type: String,
    required: true,
  },
  onlineLabel: {
    type: String,
    required: true,
  },
  avatarUrl: {
    type: String,
    required: true,
  },
  avatarFallbackUrl: {
    type: String,
    required: true,
  },
  canClose: {
    type: Boolean,
    default: true,
  },
})

const emit: EmitFn<AssistantChatHeaderEmits> = defineEmits<AssistantChatHeaderEmits>()

const closeButton: Ref<HTMLButtonElement | null> = ref(null)

/** Give the keyboard focus to the close button, the first control of an opened panel. */
function focusClose(): void {
  closeButton.value?.focus()
}

defineExpose({ focusClose })
</script>

<style scoped>
.ai-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px 12px 16px;
  background: var(--ai-card);
  border-bottom: 1px solid var(--ai-line-soft);
}
.ai-head__portrait {
  position: relative;
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--ai-accent);
}
.ai-head__dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--ai-online);
  box-shadow: 0 0 0 2px var(--ai-card);
}
.ai-head__who {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.ai-head__name {
  font-family: var(--ai-font-d);
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1.1;
  color: var(--ai-ink);
}
.ai-head__role {
  font-size: 0.74rem;
  line-height: 1.3;
  color: var(--ai-ink-dim);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.ai-head__online {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
  color: var(--ai-online);
  background: color-mix(in srgb, var(--ai-online) 12%, var(--ai-card));
  border-radius: 999px;
  padding: 4px 9px;
}
.ai-head__close {
  flex: none;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ai-ink-dim);
  display: grid;
  place-items: center;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.12s ease;
}
.ai-head__close:hover {
  background: var(--ai-paper);
  color: var(--ai-ink);
}
</style>
