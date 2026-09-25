<template>
  <component :is="props.tag" class="ai-card" @submit.prevent="onSubmit">
    <p class="ai-card__title">{{ props.title }}</p>
    <p v-if="props.note" class="ai-card__note">{{ props.note }}</p>
    <slot />
    <div class="ai-card__actions">
      <button
        :type="props.tag === 'form' ? 'submit' : 'button'"
        class="ai-card__primary"
        :disabled="props.primaryDisabled"
        @click="onPrimaryClick"
      >
        {{ props.primaryLabel }}
      </button>
      <button type="button" class="ai-card__secondary" @click="emit('secondary')">
        {{ props.secondaryLabel }}
      </button>
    </div>
  </component>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AssistantChatCardEmits, AssistantChatCardProps, AssistantChatCardTag } from '~/types/AssistantChatCard'

const props: AssistantChatCardProps = defineProps({
  title: {
    type: String,
    required: true,
  },
  note: {
    type: String,
    default: '',
  },
  tag: {
    type: String as PropType<AssistantChatCardTag>,
    default: 'div',
  },
  primaryLabel: {
    type: String,
    required: true,
  },
  primaryDisabled: {
    type: Boolean,
    default: false,
  },
  secondaryLabel: {
    type: String,
    required: true,
  },
})

const emit: EmitFn<AssistantChatCardEmits> = defineEmits<AssistantChatCardEmits>()

/** A form card confirms on submit (Enter in a field included), a plain card on the button's click. */
function onSubmit(): void {
  if (props.tag === 'form') emit('primary')
}

/** Only a plain card emits on click: a form card lets the submit event do it. */
function onPrimaryClick(): void {
  if (props.tag !== 'form') emit('primary')
}
</script>

<style scoped>
.ai-card {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line);
  border-radius: 16px;
}
.ai-card__title {
  margin: 0;
  font-family: var(--ai-font-d);
  font-size: 0.98rem;
  font-weight: 600;
  line-height: 1.25;
  color: var(--ai-ink);
}
.ai-card__note {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--ai-ink-dim);
}
.ai-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}
.ai-card__primary,
.ai-card__secondary {
  flex: 1;
  border: 0;
  border-radius: 999px;
  padding: 11px 12px;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
}
.ai-card__primary {
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
}
.ai-card__primary:disabled {
  opacity: 0.45;
  cursor: default;
}
.ai-card__secondary {
  background: transparent;
  color: var(--ai-ink-dim);
  border: 1px solid var(--ai-line);
}
</style>
