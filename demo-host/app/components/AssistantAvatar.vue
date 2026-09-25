<template>
  <img :src="props.url" :alt="props.alt" class="assistant-avatar" draggable="false" />
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
.assistant-avatar {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  user-select: none;
}
</style>
