<template>
  <header class="ai-header">
    <span class="ai-header__portrait">
      <AssistantAvatar :url="props.avatarUrl" :fallback-url="props.avatarFallbackUrl" :alt="props.assistantName" />
      <span class="ai-header__online-dot" aria-hidden="true" />
    </span>
    <span class="ai-header__identity">
      <b class="ai-header__name">{{ props.assistantName }}</b>
      <span class="ai-header__role">{{ props.roleLabel }} · {{ props.businessName }}</span>
    </span>
    <select
      v-if="props.languages.length > 1"
      class="ai-header__language"
      :aria-label="UI_LABELS[props.language].language"
      :value="props.language"
      @change="onLanguageChange"
    >
      <option v-for="code in props.languages" :key="code" :value="code">{{ LANGUAGE_LABELS[code] }}</option>
    </select>
    <span v-else class="ai-header__online">{{ props.onlineLabel }}</span>
    <button
      v-if="props.canClose"
      ref="closeButton"
      type="button"
      class="ai-header__close"
      :aria-label="UI_LABELS[props.language].close"
      @click="emit('close')"
    >
      <AssistantIcon name="close" />
    </button>
  </header>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType, Ref } from 'vue'
import { ref } from 'vue'
import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantChatHeaderEmits, AssistantChatHeaderProps } from '~/types/AssistantChatHeader'
import { LANGUAGE_LABELS, UI_LABELS } from '~/constants/AssistantWidgetLabels'

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
  language: {
    type: String as PropType<AssistantWidgetLanguage>,
    required: true,
  },
  languages: {
    type: Array as PropType<AssistantWidgetLanguage[]>,
    required: true,
  },
})

const emit: EmitFn<AssistantChatHeaderEmits> = defineEmits<AssistantChatHeaderEmits>()

const closeButton: Ref<HTMLButtonElement | null> = ref(null)

/**
 * Switch the widget's language to the one picked in the selector.
 * @param event - The change event of the selector.
 */
function onLanguageChange(event: Event): void {
  const select: HTMLSelectElement | null = event.target instanceof HTMLSelectElement ? event.target : null
  const picked: AssistantWidgetLanguage | undefined = props.languages.find(
    (offered: AssistantWidgetLanguage): boolean => offered === select?.value,
  )
  if (picked) emit('change-language', picked)
}

/** Give the keyboard focus to the close button, the first control of an opened panel. */
function focusClose(): void {
  closeButton.value?.focus()
}

defineExpose({ focusClose })
</script>

<style scoped>
.ai-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px 12px 16px;
  background: var(--ai-card);
  border-bottom: 1px solid var(--ai-line-soft);
}
.ai-header__portrait {
  position: relative;
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--ai-accent);
}
.ai-header__online-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--ai-online);
  box-shadow: 0 0 0 2px var(--ai-card);
}
.ai-header__identity {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.ai-header__name {
  font-family: var(--ai-font-display);
  font-size: 1.1rem;
  font-weight: 600;
  line-height: 1.1;
  color: var(--ai-ink);
}
.ai-header__role {
  font-size: 0.74rem;
  line-height: 1.3;
  color: var(--ai-ink-dim);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.ai-header__online {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
  color: var(--ai-online);
  background: color-mix(in srgb, var(--ai-online) 12%, var(--ai-card));
  border-radius: 999px;
  padding: 4px 9px;
}
.ai-header__language {
  flex: none;
  max-width: 120px;
  appearance: none;
  border: 1px solid var(--ai-line);
  border-radius: 999px;
  background: var(--ai-card)
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M3 4.5l3 3 3-3' fill='none' stroke='%236d665b' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")
    no-repeat right 8px center / 12px;
  color: var(--ai-ink-dim);
  font: inherit;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 4px 24px 4px 10px;
  cursor: pointer;
}
.ai-header__language:hover {
  border-color: var(--ai-ink);
  color: var(--ai-ink);
}
/* Below 16px iOS Safari zooms the whole page when the selector opens. */
@media (pointer: coarse) {
  .ai-header__language {
    font-size: 16px;
  }
}
/* A native select keeps the focus after a click: the widget shows it with its own border, not the browser's ring. */
.ai-header__language:focus,
.ai-header__language:focus-visible {
  outline: none;
  border-color: var(--ai-accent-strong);
  color: var(--ai-ink);
}
.ai-header__close {
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
.ai-header__close:hover {
  background: var(--ai-paper);
  color: var(--ai-ink);
}
.ai-header__close:focus {
  outline: none;
}
.ai-header__close:focus-visible {
  outline: 2px solid var(--ai-accent-strong);
  outline-offset: 2px;
}
</style>
