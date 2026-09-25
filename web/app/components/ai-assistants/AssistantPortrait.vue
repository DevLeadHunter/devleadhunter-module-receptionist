<template>
  <span
    class="inline-block shrink-0 overflow-hidden rounded-full"
    :class="props.sizeClass"
    :style="{ background: discBackground }"
  >
    <img
      v-if="!hasPhotoFailed"
      :src="props.url"
      alt=""
      class="h-full w-full object-cover"
      draggable="false"
      @error="notePhotoFailure"
    />
    <span v-else class="flex h-full w-full items-center justify-center font-semibold text-[var(--app-ink-soft)]">
      {{ props.name.trim().charAt(0).toUpperCase() }}
    </span>
  </span>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AssistantPortraitProps } from '~/types/AssistantPortrait'
import { portraitDiscBackground } from '~/utils/assistantPortrait'

/** The receptionist's photo on a disc tinted with the business's accent; its initial stands in when the photo is missing. */
const props: AssistantPortraitProps = defineProps({
  url: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  accentColor: {
    type: String as PropType<string | null>,
    default: null,
  },
  sizeClass: {
    type: String,
    default: 'h-10 w-10 text-sm',
  },
})

const hasPhotoFailed: Ref<boolean> = ref(false)

const discBackground: ComputedRef<string> = computed((): string => portraitDiscBackground(props.accentColor))

/** Remember that the photo failed to load, so the initial shows instead. */
function notePhotoFailure(): void {
  hasPhotoFailed.value = true
}

watch(
  (): string => props.url,
  (): void => {
    hasPhotoFailed.value = false
  },
)
</script>
