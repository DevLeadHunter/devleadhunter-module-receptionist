<template>
  <AssistantChatCard
    :title="PHOTO_LABELS[props.lang].button"
    :note="PHOTO_LABELS[props.lang].note"
    :primary-label="PHOTO_LABELS[props.lang].pick"
    :primary-disabled="props.isBusy"
    :secondary-label="LEAD_LABELS[props.lang].cancel"
    @primary="fileInput?.click()"
    @secondary="emit('cancel')"
  >
    <input ref="fileInput" type="file" accept="image/*" class="ai-photo__input" @change="onFilePicked" />
  </AssistantChatCard>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType, Ref } from 'vue'
import { ref } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantChatPhotoCardEmits, AssistantChatPhotoCardProps } from '~/types/AssistantChatPhotoCard'
import { LEAD_LABELS, PHOTO_LABELS } from '~/constants/AssistantWidgetLabels'

const props: AssistantChatPhotoCardProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
  isBusy: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<AssistantChatPhotoCardEmits> = defineEmits<AssistantChatPhotoCardEmits>()

const fileInput: Ref<HTMLInputElement | null> = ref(null)

/**
 * Hand the picked file over and clear the input, so picking the same photo again fires a change.
 * @param event - The file input's change event.
 */
function onFilePicked(event: Event): void {
  const input: HTMLInputElement = event.target as HTMLInputElement
  const file: File | undefined = input.files?.[0]
  input.value = ''
  if (file) emit('pick', file)
}
</script>

<style scoped>
.ai-photo__input {
  display: none;
}
</style>
