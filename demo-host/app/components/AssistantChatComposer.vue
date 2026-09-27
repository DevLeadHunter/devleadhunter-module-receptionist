<template>
  <form class="ai-compose" :class="{ 'ai-compose--compact': props.isCompact }" @submit.prevent="emit('send')">
    <div class="ai-compose__tools">
      <button
        type="button"
        class="ai-compose__tool ai-compose__tool--more"
        :class="{ 'ai-compose__tool--open': isToolMenuOpen }"
        :aria-label="UI_LABELS[props.lang].more"
        :aria-expanded="isToolMenuOpen"
        :disabled="props.isBusy || (!props.canSendPhoto && !props.canBook)"
        @click="toggleToolMenu"
      >
        <AssistantIcon name="plus" />
      </button>
      <div v-if="isToolMenuOpen" class="ai-compose__menu" role="menu">
        <button
          type="button"
          role="menuitem"
          class="ai-compose__item"
          :disabled="!props.canSendPhoto"
          @click="pickTool('photo')"
        >
          <AssistantIcon name="camera" />
          <span>{{ PHOTO_LABELS[props.lang].button }}</span>
        </button>
        <button
          type="button"
          role="menuitem"
          class="ai-compose__item"
          :disabled="!props.canBook"
          @click="pickTool('appointment')"
        >
          <AssistantIcon name="calendar" />
          <span>{{ APPOINTMENT_LABELS[props.lang].button }}</span>
        </button>
      </div>
      <button
        type="button"
        class="ai-compose__tool ai-compose__tool--wide"
        :aria-label="PHOTO_LABELS[props.lang].button"
        :title="PHOTO_LABELS[props.lang].button"
        :disabled="props.isBusy || !props.canSendPhoto"
        @click="emit('photo')"
      >
        <AssistantIcon name="camera" />
      </button>
      <button
        type="button"
        class="ai-compose__tool ai-compose__tool--wide"
        :aria-label="APPOINTMENT_LABELS[props.lang].button"
        :title="APPOINTMENT_LABELS[props.lang].button"
        :disabled="props.isBusy || !props.canBook"
        @click="emit('appointment')"
      >
        <AssistantIcon name="calendar" />
      </button>
    </div>
    <textarea
      :value="props.modelValue"
      rows="1"
      maxlength="2000"
      :placeholder="UI_PLACEHOLDER[props.lang]"
      :aria-label="UI_LABELS[props.lang].message"
      @input="onInput"
      @focus="closeToolMenu"
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
import type { EmitFn, PropType, Ref } from 'vue'
import { onBeforeUnmount, ref, watch } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type {
  AssistantChatComposerEmits,
  AssistantChatComposerProps,
  AssistantChatComposerTool,
} from '~/types/AssistantChatComposer'
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
  isCompact: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<AssistantChatComposerEmits> = defineEmits<AssistantChatComposerEmits>()

/** On a narrow bar the two actions fold behind one « + »; this is the menu it unfolds. */
const isToolMenuOpen: Ref<boolean> = ref(false)

/**
 * Report what the visitor types.
 * @param event - The textarea's input event.
 */
function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}

/** Unfold or fold the actions menu. */
function toggleToolMenu(): void {
  isToolMenuOpen.value = !isToolMenuOpen.value
}

/** Fold the actions menu. */
function closeToolMenu(): void {
  isToolMenuOpen.value = false
}

/**
 * Trigger an action from the folded menu and fold it.
 * @param tool - The action picked.
 */
function pickTool(tool: AssistantChatComposerTool): void {
  closeToolMenu()
  if (tool === 'photo') emit('photo')
  else emit('appointment')
}

/**
 * Fold the menu when the visitor taps elsewhere in the widget or presses Escape.
 * @param event - The document's pointer or keyboard event.
 */
function onDocumentInteraction(event: Event): void {
  if (event instanceof KeyboardEvent) {
    if (event.key === 'Escape') closeToolMenu()
    return
  }
  const target: EventTarget | null = event.target
  if (target instanceof Element && target.closest('.ai-compose__tools')) return
  closeToolMenu()
}

watch(isToolMenuOpen, (isShown: boolean): void => {
  if (isShown) {
    document.addEventListener('pointerdown', onDocumentInteraction, true)
    document.addEventListener('keydown', onDocumentInteraction, true)
  } else {
    document.removeEventListener('pointerdown', onDocumentInteraction, true)
    document.removeEventListener('keydown', onDocumentInteraction, true)
  }
})

onBeforeUnmount((): void => {
  document.removeEventListener('pointerdown', onDocumentInteraction, true)
  document.removeEventListener('keydown', onDocumentInteraction, true)
})
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
.ai-compose__tools {
  position: relative;
  display: flex;
  gap: 8px;
  flex: none;
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
    color 0.12s ease,
    transform 0.18s ease;
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
/* Wide bar: the two actions side by side, the « + » stays out of the way. */
.ai-compose__tool--more {
  display: none;
}
/* Narrow bar (a phone): one « + » and a taller field; the actions unfold above it with their names. */
.ai-compose--compact .ai-compose__tool--more {
  display: grid;
}
.ai-compose--compact .ai-compose__tool--wide {
  display: none;
}
.ai-compose__tool--open {
  transform: rotate(45deg);
  border-color: var(--ai-ink);
  color: var(--ai-ink);
}
.ai-compose__menu {
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  z-index: 5;
  display: grid;
  gap: 2px;
  min-width: 250px;
  padding: 6px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line);
  border-radius: 14px;
  box-shadow: 0 18px 40px -22px rgba(23, 19, 13, 0.45);
}
.ai-compose__item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 8px 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--ai-ink);
  font: inherit;
  font-size: 15px;
  text-align: left;
  cursor: pointer;
}
.ai-compose__item:hover {
  background: var(--ai-paper-2);
}
.ai-compose__item:disabled {
  opacity: 0.4;
  cursor: default;
}
.ai-compose__item .assistant-icon {
  font-size: 18px;
  color: var(--ai-accent-strong);
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
