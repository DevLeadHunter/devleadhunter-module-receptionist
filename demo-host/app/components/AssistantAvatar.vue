<template>
  <span class="assistant-avatar">
    <img :src="props.url" :alt="props.alt" class="assistant-avatar__photo" draggable="false" />
    <i class="assistant-avatar__tint" aria-hidden="true" />
    <i class="assistant-avatar__light" aria-hidden="true" />
  </span>
</template>

<script lang="ts" setup>
import type { AssistantAvatarProps } from '~/types/AssistantAvatar'

const props: AssistantAvatarProps = defineProps({
  url: {
    type: String,
    required: true,
  },
  alt: {
    type: String,
    required: true,
  },
})
</script>

<style scoped>
/* The portrait is lit in the business's colour: a neutral studio photo takes the accent like a coloured gel. */
.assistant-avatar {
  position: relative;
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  isolation: isolate;
  background: radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--ai-accent) 55%, white), var(--ai-accent) 75%);
  user-select: none;
}
.assistant-avatar__photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(0.9) contrast(1.05);
}
.assistant-avatar__tint,
.assistant-avatar__light {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.assistant-avatar__tint {
  background: var(--ai-accent);
  mix-blend-mode: color;
  opacity: 0.5;
}
.assistant-avatar__light {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--ai-accent) 60%, transparent),
    transparent 55%,
    color-mix(in srgb, var(--ai-accent) 35%, transparent)
  );
  mix-blend-mode: soft-light;
}
</style>
