<template>
  <button
    ref="rootElement"
    type="button"
    class="ai-launcher"
    :class="{ 'ai-launcher--mobile': props.isMobileLayout }"
    :aria-label="`Ouvrir ${props.assistantName}`"
    @click="emit('open')"
  >
    <span class="ai-launcher__say">
      Une question&nbsp;? <strong>{{ props.assistantName }}</strong> vous répond, 24h/24.
    </span>
    <span class="ai-launcher__portrait" aria-hidden="true">
      <AssistantAvatar :url="props.avatarUrl" :alt="props.assistantName" />
      <i class="ai-launcher__dot" />
    </span>
  </button>
</template>

<script lang="ts" setup>
import type { EmitFn, Ref } from 'vue'
import { ref } from 'vue'
import type { AssistantChatLauncherEmits, AssistantChatLauncherProps } from '~/types/AssistantChatLauncher'

const props: AssistantChatLauncherProps = defineProps({
  assistantName: {
    type: String,
    required: true,
  },
  avatarUrl: {
    type: String,
    required: true,
  },
  isMobileLayout: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<AssistantChatLauncherEmits> = defineEmits<AssistantChatLauncherEmits>()

/** The button itself, measured by the parent to size the loader's iframe, and focused when the panel closes. */
const rootElement: Ref<HTMLButtonElement | null> = ref(null)

/** Give the keyboard focus to the launcher. */
function focus(): void {
  rootElement.value?.focus()
}

defineExpose({ rootElement, focus })
</script>

<style scoped>
.ai-launcher {
  position: fixed;
  right: max(22px, env(safe-area-inset-right, 0px));
  bottom: max(22px, env(safe-area-inset-bottom, 0px));
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font-family: var(--ai-font-b);
}
.ai-launcher__say {
  background: var(--ai-card);
  color: var(--ai-ink);
  border: 1px solid var(--ai-line);
  border-radius: 14px;
  padding: 10px 14px;
  font-size: 0.85rem;
  line-height: 1.4;
  max-width: 220px;
  text-align: left;
  box-shadow: 0 18px 44px -24px rgba(23, 19, 13, 0.45);
}
.ai-launcher__say strong {
  font-family: var(--ai-font-d);
  font-weight: 600;
}
.ai-launcher__portrait {
  position: relative;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  box-shadow:
    0 0 0 3px var(--ai-card),
    0 0 0 4px var(--ai-accent-strong),
    0 12px 28px -12px rgba(23, 19, 13, 0.55);
  transition: transform 0.15s ease;
}
.ai-launcher:hover .ai-launcher__portrait {
  transform: translateY(-2px);
}
.ai-launcher__dot {
  position: absolute;
  right: 2px;
  bottom: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--ai-online);
  box-shadow: 0 0 0 2px var(--ai-card);
}
.ai-launcher--mobile .ai-launcher__say {
  display: none;
}
</style>
