<template>
  <span class="assistant-avatar" role="img" :aria-label="props.name">
    <span class="assistant-avatar__initial" aria-hidden="true">{{ initial }}</span>
  </span>
</template>

<script lang="ts" setup>
import type { ComputedRef } from 'vue'
import { computed } from 'vue'
import type { AssistantAvatarProps } from '~/types/AssistantAvatar'

const props: AssistantAvatarProps = defineProps({
  name: {
    type: String,
    required: true,
  },
})

/** The first letter of the name, upper case; « A » when the name is empty. */
const initial: ComputedRef<string> = computed((): string => props.name.trim().charAt(0).toUpperCase() || 'A')
</script>

<style scoped>
.assistant-avatar {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  background: var(--ai-accent-strong, #7a5729);
  color: var(--ai-on-strong, #ffffff);
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 600;
  line-height: 1;
  user-select: none;
}
.assistant-avatar__initial {
  /* Sized by the parent's font-size, so the launcher and the header share one mark at two sizes. */
  font-size: inherit;
  transform: translateY(0.04em);
}
</style>
