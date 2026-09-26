<template>
  <AssistantChatCard
    tag="form"
    :title="labels.title"
    :note="props.pickedSummary"
    :primary-label="labels.send"
    :primary-disabled="props.isSubmitting || !canSubmit"
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
      ref="contactInput"
      v-model="contact"
      class="ai-field"
      :class="{ 'ai-field--invalid': showContactHint }"
      maxlength="255"
      autocomplete="tel"
      :placeholder="labels.contact"
      :aria-label="labels.contact"
      :aria-invalid="showContactHint"
      @blur="hasLeftContactField = true"
    />
    <p v-if="showContactHint" class="ai-field__hint" aria-live="polite">{{ labels.contactHint }}</p>
    <input
      ref="needInput"
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
import { VisitorContactUtils } from '~/utils/VisitorContactUtils'

const props: AssistantChatContactFormProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
  pickedSummary: {
    type: String,
    default: '',
  },
  initialName: {
    type: String,
    default: '',
  },
  initialContact: {
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
const contactInput: Ref<HTMLInputElement | null> = ref(null)
const needInput: Ref<HTMLInputElement | null> = ref(null)
const name: Ref<string> = ref(props.initialName)
const contact: Ref<string> = ref(props.initialContact)
const need: Ref<string> = ref(props.initialNeed)
const hasLeftContactField: Ref<boolean> = ref(false)

const labels: ComputedRef<AssistantLeadLabels> = computed((): AssistantLeadLabels => LEAD_LABELS[props.lang])
/** The business can dial or write to what the visitor typed: a phone number or an email address. */
const isContactReachable: ComputedRef<boolean> = computed((): boolean => VisitorContactUtils.isReachable(contact.value))
const canSubmit: ComputedRef<boolean> = computed(
  (): boolean => name.value.trim().length > 0 && isContactReachable.value,
)
/** The hint waits for the visitor to leave the field: a number still being typed is not wrong yet. */
const showContactHint: ComputedRef<boolean> = computed(
  (): boolean => hasLeftContactField.value && contact.value.trim().length > 0 && !isContactReachable.value,
)

/** Give the keyboard focus to the first field still to fill: the name, the contact, then the need. */
function focusFirstEmptyField(): void {
  if (!name.value.trim()) nameInput.value?.focus()
  else if (!isContactReachable.value) contactInput.value?.focus()
  else needInput.value?.focus()
}

// What the visitor gives in the chat after the form opened fills the fields they have not typed yet.
watch(
  (): string => props.initialName,
  (prefill: string): void => {
    if (prefill && !name.value.trim()) name.value = prefill
  },
)
watch(
  (): string => props.initialContact,
  (prefill: string): void => {
    if (prefill && !contact.value.trim()) contact.value = prefill
  },
)
watch(
  (): string => props.initialNeed,
  (prefill: string): void => {
    if (prefill && !need.value.trim()) need.value = prefill
  },
)

defineExpose({ focusFirstEmptyField })
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
.ai-field--invalid {
  border-color: var(--ai-ink-dim);
}
.ai-field__hint {
  margin: -2px 0 0 4px;
  font-size: 0.82rem;
  line-height: 1.35;
  color: var(--ai-ink-dim);
}
</style>
