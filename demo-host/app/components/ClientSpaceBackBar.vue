<template>
  <header class="cs-bar">
    <button type="button" class="cs-bar__back" @click="emit('back')">
      <ClientSpaceIcon name="chevron-left" />{{ props.backLabel }}
    </button>
    <span v-if="props.title" class="cs-bar__title cs-bar__title--center">{{ props.title }}</span>
  </header>
</template>

<script lang="ts" setup>
import type { EmitFn } from 'vue'
import type { ClientSpaceBackBarEmits, ClientSpaceBackBarProps } from '~/types/ClientSpaceBackBar'

const props: ClientSpaceBackBarProps = defineProps({
  backLabel: { type: String, required: true },
  title: { type: String, default: '' },
})

const emit: EmitFn<ClientSpaceBackBarEmits> = defineEmits<ClientSpaceBackBarEmits>()
</script>
