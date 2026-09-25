<template>
  <span class="assistant-avatar">
    <img
      ref="photoElement"
      :src="shownUrl"
      :alt="props.alt"
      class="assistant-avatar__photo"
      draggable="false"
      @error="showFallback"
    />
  </span>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, ref, watch } from 'vue'
import type { AssistantAvatarProps } from '~/types/AssistantAvatar'

const props: AssistantAvatarProps = defineProps({
  url: {
    type: String,
    required: true,
  },
  fallbackUrl: {
    type: String,
    required: true,
  },
  alt: {
    type: String,
    required: true,
  },
})

const photoElement: Ref<HTMLImageElement | null> = ref(null)
const hasPhotoFailed: Ref<boolean> = ref(false)

const shownUrl: ComputedRef<string> = computed((): string => (hasPhotoFailed.value ? props.fallbackUrl : props.url))

/** Show the drawn bust when the persona's photo is not shipped. */
function showFallback(): void {
  hasPhotoFailed.value = true
}

watch(
  (): string => props.url,
  (): void => {
    hasPhotoFailed.value = false
  },
)

onMounted((): void => {
  // Server-rendered, the photo may have failed before the error listener was attached: read the outcome off the element.
  const photo: HTMLImageElement | null = photoElement.value
  if (photo && photo.complete && photo.naturalWidth === 0) showFallback()
})
</script>

<style scoped>
.assistant-avatar {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  background: var(--ai-accent-tint);
  user-select: none;
}
.assistant-avatar__photo {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
