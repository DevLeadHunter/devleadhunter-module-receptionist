<template>
  <div class="grid grid-cols-3 gap-2" role="group" aria-label="Réceptionniste">
    <button
      v-for="persona in ASSISTANT_CASTING"
      :key="persona.slug"
      type="button"
      class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border px-2 py-3 text-xs transition-colors"
      :class="
        isPicked(persona)
          ? 'border-[var(--app-ink)] bg-[var(--app-surface-2)]'
          : 'border-[var(--app-line)] hover:border-[var(--app-ink-soft)]'
      "
      :aria-pressed="isPicked(persona)"
      @click="pick(persona)"
    >
      <AssistantPortrait
        :url="personaPortraitUrl(props.demoUrl, persona.slug)"
        :name="persona.name"
        :accent-color="props.accentColor"
        size-class="h-14 w-14 text-base"
      />
      <span class="font-medium text-[var(--app-ink)]">{{ persona.name }}</span>
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { ModelRef, PropType } from 'vue'
import type { AiAssistantPersona } from '~/types/AiAssistant'
import type { AssistantPersonaPickerProps } from '~/types/AssistantPersonaPicker'
import AssistantPortrait from '~/components/ai-assistants/AssistantPortrait.vue'
import { ASSISTANT_CASTING } from '~/constants/assistantCasting'
import { personaPortraitUrl } from '~/utils/assistantPortrait'

/** The first name shown by the assistant; a casting persona is picked when it is its name. */
const modelValue: ModelRef<string> = defineModel<string>({ required: true })

/** Grid of the six receptionists (portrait and first name); the picked one is the assistant's first name. */
const props: AssistantPersonaPickerProps = defineProps({
  demoUrl: {
    type: String,
    required: true,
  },
  accentColor: {
    type: String as PropType<string | null>,
    default: null,
  },
})

/**
 * Whether a persona is the one named by the form.
 * @param persona - A casting persona.
 * @returns True when its name is the assistant's first name, whatever the case.
 */
function isPicked(persona: AiAssistantPersona): boolean {
  return modelValue.value.trim().toLowerCase() === persona.name.toLowerCase()
}

/**
 * Name the assistant after the persona.
 * @param persona - The picked persona.
 */
function pick(persona: AiAssistantPersona): void {
  modelValue.value = persona.name
}
</script>
