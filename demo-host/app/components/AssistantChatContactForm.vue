<template>
  <AssistantChatCard
    tag="form"
    :title="labels.title"
    :note="props.pickedSummary"
    :primary-label="labels.send"
    :primary-disabled="props.isSubmitting || !name.trim() || !contact.trim()"
    :secondary-label="labels.cancel"
    @primary="emit('submit', { name, contact, need })"
    @secondary="emit('cancel')"
  >
    <input
      ref="nameInput"
      v-model="name"
      class="ai-field"
      maxlength="255"
      autocomplete="name"
      :placeholder="labels.name"
      :aria-label="labels.name"
    />
    <input
      v-model="contact"
      class="ai-field"
      maxlength="255"
      autocomplete="tel"
      :placeholder="labels.contact"
      :aria-label="labels.contact"
    />
    <input
      v-model="need"
      class="ai-field"
      maxlength="2000"
      autocomplete="off"
      :placeholder="labels.need"
      :aria-label="labels.need"
    />
  </AssistantChatCard>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AssistantLeadLabels, AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantChatContactFormEmits, AssistantChatContactFormProps } from '~/types/AssistantChatContactForm'
import { LEAD_LABELS } from '~/constants/AssistantWidgetLabels'

const props: AssistantChatContactFormProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
  pickedSummary: {
    type: String,
    default: '',
  },
  initialNeed: {
    type: String,
    default: '',
  },
  isSubmitting: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<AssistantChatContactFormEmits> = defineEmits<AssistantChatContactFormEmits>()

const nameInput: Ref<HTMLInputElement | null> = ref(null)
const name: Ref<string> = ref('')
const contact: Ref<string> = ref('')
const need: Ref<string> = ref(props.initialNeed)

const labels: ComputedRef<AssistantLeadLabels> = computed((): AssistantLeadLabels => LEAD_LABELS[props.lang])

/** Give the keyboard focus to the name field. */
function focusName(): void {
  nameInput.value?.focus()
}

// A photo described after the form opened fills the need the visitor has not typed yet.
watch(
  (): string => props.initialNeed,
  (prefill: string): void => {
    if (prefill && !need.value.trim()) need.value = prefill
  },
)

defineExpose({ focusName })
</script>

<style scoped>
.ai-field {
  border: 1px solid var(--ai-line);
  border-radius: 12px;
  padding: 10px 12px;
  font: inherit;
  /* 16px minimum: stops iOS Safari from zooming the page on focus. */
  font-size: 16px;
  background: var(--ai-paper-2);
  color: var(--ai-ink);
}
.ai-field:focus {
  outline: 2px solid var(--ai-accent-strong);
  outline-offset: 1px;
}
</style>
