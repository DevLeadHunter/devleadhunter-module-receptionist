<template>
  <AssistantChatCard
    tag="form"
    novalidate
    :title="labels.title"
    :note="props.pickedSummary"
    :primary-label="labels.send"
    :primary-disabled="props.isSubmitting || !canSubmit"
    :secondary-label="labels.cancel"
    @primary="submit"
    @secondary="emit('cancel')"
  >
    <label class="ai-contact-form__label" :for="nameFieldId">{{ labels.name }}</label>
    <input
      :id="nameFieldId"
      ref="nameInput"
      v-model="name"
      class="ai-contact-form__field"
      type="text"
      maxlength="255"
      autocomplete="name"
      autocapitalize="words"
      enterkeyhint="next"
    />

    <fieldset class="ai-contact-form__channels">
      <legend class="ai-contact-form__label">{{ labels.contactBy }}</legend>
      <div class="ai-contact-form__channel-options">
        <label
          v-for="channel in CONTACT_CHANNELS"
          :key="channel"
          class="ai-contact-form__channel"
          :class="{ 'ai-contact-form__channel--picked': contactChannel === channel }"
        >
          <input
            v-model="contactChannel"
            class="ai-contact-form__channel-input"
            type="radio"
            :name="channelGroupName"
            :value="channel"
          />
          {{ channel === 'phone' ? labels.phone : labels.email }}
        </label>
      </div>
    </fieldset>
    <input
      ref="contactInput"
      v-model="contact"
      class="ai-contact-form__field"
      :class="{ 'ai-contact-form__field--invalid': showContactHint }"
      :type="contactChannel === 'phone' ? 'tel' : 'email'"
      :inputmode="contactChannel === 'phone' ? 'tel' : 'email'"
      :autocomplete="contactChannel === 'phone' ? 'tel' : 'email'"
      maxlength="255"
      enterkeyhint="next"
      :aria-label="contactChannel === 'phone' ? labels.phone : labels.email"
      :aria-invalid="showContactHint"
      :aria-describedby="showContactHint ? hintId : undefined"
      @blur="hasLeftContactField = true"
    />
    <p v-if="showContactHint" :id="hintId" class="ai-contact-form__hint" aria-live="polite">
      {{ labels.contactHint }}
    </p>

    <label class="ai-contact-form__label" :for="needFieldId">{{ labels.need }}</label>
    <input
      :id="needFieldId"
      ref="needInput"
      v-model="need"
      class="ai-contact-form__field"
      type="text"
      maxlength="2000"
      autocomplete="off"
      enterkeyhint="send"
    />
  </AssistantChatCard>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, useId, watch } from 'vue'
import type { AssistantContactChannel, AssistantLeadLabels, AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantChatContactFormEmits, AssistantChatContactFormProps } from '~/types/AssistantChatContactForm'
import { LEAD_LABELS } from '~/constants/AssistantWidgetLabels'
import { VisitorContactUtils } from '~/utils/VisitorContactUtils'

const props: AssistantChatContactFormProps = defineProps({
  language: {
    type: String as PropType<AssistantWidgetLanguage>,
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

const nameFieldId: string = useId()
const needFieldId: string = useId()
const hintId: string = useId()
const channelGroupName: string = useId()

const CONTACT_CHANNELS: AssistantContactChannel[] = ['phone', 'email']

const nameInput: Ref<HTMLInputElement | null> = ref(null)
const contactInput: Ref<HTMLInputElement | null> = ref(null)
const needInput: Ref<HTMLInputElement | null> = ref(null)
const name: Ref<string> = ref(props.initialName)
const contact: Ref<string> = ref(props.initialContact)
const need: Ref<string> = ref(props.initialNeed)
const contactChannel: Ref<AssistantContactChannel> = ref(channelOf(props.initialContact))
const hasLeftContactField: Ref<boolean> = ref(false)

const labels: ComputedRef<AssistantLeadLabels> = computed((): AssistantLeadLabels => LEAD_LABELS[props.language])
/** The business can dial the number, or write to the address, the visitor typed for the channel they picked. */
const isContactReachable: ComputedRef<boolean> = computed((): boolean =>
  contactChannel.value === 'phone'
    ? VisitorContactUtils.isPhone(contact.value)
    : VisitorContactUtils.isEmail(contact.value),
)
const canSubmit: ComputedRef<boolean> = computed(
  (): boolean => name.value.trim().length > 0 && isContactReachable.value,
)
/** The hint waits for the visitor to leave the field: a number still being typed is not wrong yet. */
const showContactHint: ComputedRef<boolean> = computed(
  (): boolean => hasLeftContactField.value && contact.value.trim().length > 0 && !isContactReachable.value,
)

/**
 * The channel a contact reads as: an address is an email, anything else is dialled.
 * @param value - A contact, as the chat gave it.
 * @returns Its channel.
 */
function channelOf(value: string): AssistantContactChannel {
  return VisitorContactUtils.isEmail(value) ? 'email' : 'phone'
}

/** Hand the details over, trimmed. */
function submit(): void {
  emit('submit', { name: name.value.trim(), contact: contact.value.trim(), need: need.value.trim() })
}

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
    if (!prefill || contact.value.trim()) return
    contact.value = prefill
    contactChannel.value = channelOf(prefill)
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
.ai-contact-form__label {
  margin: 2px 0 -2px 2px;
  padding: 0;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.3;
  color: var(--ai-ink);
}
.ai-contact-form__field {
  border: 1px solid var(--ai-line);
  border-radius: 12px;
  padding: 10px 12px;
  font: inherit;
  /* 16px minimum: stops iOS Safari from zooming the page on focus. */
  font-size: 16px;
  background: var(--ai-paper-2);
  color: var(--ai-ink);
}
.ai-contact-form__field:focus {
  outline: 2px solid var(--ai-accent-strong);
  outline-offset: 1px;
}
.ai-contact-form__field--invalid {
  border-color: var(--ai-ink-dim);
}
.ai-contact-form__hint {
  margin: -2px 0 0 4px;
  font-size: 0.82rem;
  line-height: 1.35;
  color: var(--ai-ink-dim);
}
.ai-contact-form__channels {
  display: grid;
  gap: 8px;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
.ai-contact-form__channel-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ai-contact-form__channel {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 6px 14px;
  border: 1px solid var(--ai-line);
  border-radius: 999px;
  background: var(--ai-paper-2);
  color: var(--ai-ink);
  font-size: 0.85rem;
  cursor: pointer;
}
.ai-contact-form__channel--picked {
  border-color: var(--ai-accent-strong);
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
}
.ai-contact-form__channel:focus-within {
  outline: 2px solid var(--ai-accent-strong);
  outline-offset: 2px;
}
.ai-contact-form__channel-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
</style>
