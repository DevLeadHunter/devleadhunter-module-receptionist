<template>
  <a
    v-if="prospectAssistant"
    :href="assistantDemoUrl"
    target="_blank"
    rel="noopener noreferrer"
    class="btn-primary w-full"
  >
    <UIcon name="i-lucide-external-link" class="mr-1.5 h-4 w-4" />Ouvrir l'assistant
  </a>
  <button v-else class="btn-primary w-full" :disabled="isGeneratingAssistant" @click="generateAssistant">
    <UIcon
      :name="isGeneratingAssistant ? 'i-lucide-loader-circle' : 'i-lucide-bot'"
      :class="['mr-1.5 h-4 w-4', isGeneratingAssistant && 'animate-spin']"
    />
    {{ isGeneratingAssistant ? 'Génération…' : 'Générer un assistant IA' }}
  </button>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { Prospect } from '~/types'
import type { AssistantProspectPrimaryActionProps } from '../../types/AssistantProspectPrimaryAction'
import type { UseProspectAssistantReturn } from '../../composables/useProspectAssistant'
import { useProspectAssistant } from '../../composables/useProspectAssistant'

const props: AssistantProspectPrimaryActionProps = defineProps({
  prospect: {
    type: Object as PropType<Prospect>,
    required: true,
  },
  openingId: {
    type: Number,
    required: true,
  },
})

const { prospectAssistant, assistantDemoUrl, isGeneratingAssistant, generateAssistant }: UseProspectAssistantReturn =
  useProspectAssistant(props)
</script>
