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
      <span class="h-14 w-14 overflow-hidden rounded-full bg-[var(--app-surface-2)]">
        <img
          v-if="!failedSlugs.includes(persona.slug)"
          :src="portraitUrl(persona)"
          alt=""
          class="h-full w-full object-cover"
          draggable="false"
          @error="notePortraitFailure(persona)"
        />
        <span
          v-else
          class="flex h-full w-full items-center justify-center text-sm font-semibold text-[var(--app-ink-soft)]"
        >
          {{ persona.name.charAt(0) }}
        </span>
      </span>
      <span class="font-medium text-[var(--app-ink)]">{{ persona.name }}</span>
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { ModelRef, Ref } from 'vue'
import { ref } from 'vue'
import type { AiAssistantPersona } from '~/types/AiAssistant'
import type { AssistantPersonaPickerProps } from '~/types/AssistantPersonaPicker'
import { ASSISTANT_CASTING } from '~/constants/assistantCasting'

/** The first name shown by the assistant; a casting persona is picked when it is its name. */
const modelValue: ModelRef<string> = defineModel<string>({ required: true })

/** Grid of the six receptionists (portrait and first name); the picked one is the assistant's first name. */
const props: AssistantPersonaPickerProps = defineProps({
  portraitBaseUrl: {
    type: String,
    required: true,
  },
})

/** Personas whose portrait the demo host does not serve: their initial stands in. */
const failedSlugs: Ref<string[]> = ref([])

/**
 * Whether a persona is the one named by the form.
 * @param persona - A casting persona.
 * @returns True when its name is the assistant's first name, whatever the case.
 */
function isPicked(persona: AiAssistantPersona): boolean {
  return modelValue.value.trim().toLowerCase() === persona.name.toLowerCase()
}

/**
 * The persona's portrait on the demo host.
 * @param persona - A casting persona.
 * @returns The image address.
 */
function portraitUrl(persona: AiAssistantPersona): string {
  return `${props.portraitBaseUrl}/avatars/${persona.slug}.webp`
}

/**
 * Name the assistant after the persona.
 * @param persona - The picked persona.
 */
function pick(persona: AiAssistantPersona): void {
  modelValue.value = persona.name
}

/**
 * Remember that the persona's portrait failed to load, so its initial shows instead.
 * @param persona - The persona whose image errored.
 */
function notePortraitFailure(persona: AiAssistantPersona): void {
  if (!failedSlugs.value.includes(persona.slug)) failedSlugs.value = [...failedSlugs.value, persona.slug]
}
</script>
