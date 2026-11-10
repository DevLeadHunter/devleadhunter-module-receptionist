<template>
  <div class="space-y-3 px-5 py-4">
    <div class="flex items-center justify-between gap-3">
      <p class="text-[10px] font-semibold tracking-wider text-[var(--app-ink-soft)] uppercase">Réceptionniste IA</p>
      <a
        v-if="prospectAssistant"
        :href="assistantDemoUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="btn-secondary text-xs"
      >
        <UIcon name="i-lucide-external-link" class="h-3.5 w-3.5" />
        Ouvrir
      </a>
      <button
        v-else
        type="button"
        class="btn-secondary text-xs"
        :disabled="isGeneratingAssistant"
        @click="generateAssistant"
      >
        <UIcon
          :name="isGeneratingAssistant ? 'i-lucide-loader-circle' : 'i-lucide-bot'"
          :class="['h-3.5 w-3.5', isGeneratingAssistant && 'animate-spin']"
        />
        {{ isGeneratingAssistant ? 'Génération…' : 'Générer' }}
      </button>
    </div>
    <p class="text-xs leading-relaxed text-[var(--app-ink-soft)]">
      Assistant multilingue branché sur les données de ce prospect, à tester sur sa page démo.
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { Prospect } from '~/types'
import type { AssistantProspectSectionEmits, AssistantProspectSectionProps } from '../../types/AssistantProspectSection'
import type { UseProspectAssistantReturn } from '../../composables/useProspectAssistant'
import { useProspectAssistant } from '../../composables/useProspectAssistant'

const props: AssistantProspectSectionProps = defineProps({
  prospect: {
    type: Object as PropType<Prospect>,
    required: true,
  },
  openingId: {
    type: Number,
    required: true,
  },
})

defineEmits<AssistantProspectSectionEmits>()

const { prospectAssistant, assistantDemoUrl, isGeneratingAssistant, generateAssistant }: UseProspectAssistantReturn =
  useProspectAssistant(props)
</script>
