<template>
  <div class="grid grid-cols-4 gap-2" role="group" aria-label="Réceptionniste">
    <button
      v-for="persona in ASSISTANT_CASTING"
      :key="persona.slug"
      type="button"
      class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border px-1 py-2.5 text-xs transition-colors"
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
        size-class="h-12 w-12 text-sm"
      />
      <span class="font-medium text-[var(--app-ink)]">{{ persona.name }}</span>
    </button>
    <button
      type="button"
      class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border px-1 py-2.5 text-xs transition-colors"
      :class="customImageCardClass"
      :aria-pressed="isCustomImagePicked"
      :aria-label="
        props.customImageUrl ? 'Votre image : la choisir ou la modifier' : 'Votre image : ajouter une photo ou un logo'
      "
      @click="emit('customize')"
    >
      <span class="relative">
        <AssistantPortrait
          v-if="props.customImageUrl"
          :url="props.customImageUrl"
          :name="modelValue"
          :accent-color="props.accentColor"
          :background="props.customImageBackground"
          size-class="h-12 w-12 text-sm"
        />
        <span
          v-else
          class="flex h-12 w-12 items-center justify-center rounded-full border border-dashed border-[var(--app-ink-soft)] text-[var(--app-ink-soft)]"
        >
          <UIcon name="i-lucide-plus" class="h-5 w-5" />
        </span>
        <span
          v-if="props.customImageUrl"
          class="absolute -right-1 -bottom-1 flex h-5 w-5 items-center justify-center rounded-full border border-[var(--app-line)] bg-[var(--app-surface)] text-[var(--app-ink)]"
          aria-hidden="true"
        >
          <UIcon name="i-lucide-pencil" class="h-2.5 w-2.5" />
        </span>
      </span>
      <span class="font-medium whitespace-nowrap text-[var(--app-ink)]">Votre image</span>
    </button>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, ModelRef, PropType } from 'vue'
import type { AiAssistantPersona } from '~/types/AiAssistant'
import type { AssistantPersonaPickerEmits, AssistantPersonaPickerProps } from '~/types/AssistantPersonaPicker'
import { computed } from 'vue'
import AssistantPortrait from '~/components/ai-assistants/AssistantPortrait.vue'
import { ASSISTANT_CASTING } from '~/constants/assistantCasting'
import { personaPortraitUrl } from '~/utils/assistantPortrait'

/** The first name shown by the assistant; a casting persona is picked when it is its name. */
const modelValue: ModelRef<string> = defineModel<string>({ required: true })

/** Whether the business's own image shows in place of a casting face. */
const isCustomImagePicked: ModelRef<boolean> = defineModel<boolean>('customImagePicked', { required: true })

/** Grid of the six receptionists (portrait and first name), then the business's own image, the last card. */
const props: AssistantPersonaPickerProps = defineProps({
  demoUrl: {
    type: String,
    required: true,
  },
  accentColor: {
    type: String as PropType<string | null>,
    default: null,
  },
  customImageUrl: {
    type: String as PropType<string | null>,
    default: null,
  },
  customImageBackground: {
    type: String as PropType<string | null>,
    default: null,
  },
})

const emit: EmitFn<AssistantPersonaPickerEmits> = defineEmits<AssistantPersonaPickerEmits>()

const customImageCardClass: ComputedRef<string> = computed((): string => {
  if (isCustomImagePicked.value) return 'border-[var(--app-ink)] bg-[var(--app-surface-2)]'
  return props.customImageUrl
    ? 'border-[var(--app-line)] hover:border-[var(--app-ink-soft)]'
    : 'border-dashed border-[var(--app-line)] hover:border-[var(--app-ink-soft)]'
})

/**
 * Whether a persona is the one shown: its name is the form's, and no image of the business takes its place.
 * @param persona - A casting persona.
 * @returns True when it is the face the receptionist shows.
 */
function isPicked(persona: AiAssistantPersona): boolean {
  return !isCustomImagePicked.value && modelValue.value.trim().toLowerCase() === persona.name.toLowerCase()
}

/**
 * Name the assistant after the persona, whose face then shows in place of the business's image.
 * @param persona - The picked persona.
 */
function pick(persona: AiAssistantPersona): void {
  modelValue.value = persona.name
  isCustomImagePicked.value = false
}
</script>
