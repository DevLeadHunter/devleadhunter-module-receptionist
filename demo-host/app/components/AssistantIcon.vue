<template>
  <component :is="GLYPHS[props.name]" class="assistant-icon" />
</template>

<script lang="ts" setup>
import type { Component, PropType } from 'vue'
import type { AssistantIconName, AssistantIconProps } from '../types/AssistantIcon'
import AssistantIconCalendar from './AssistantIconCalendar.vue'
import AssistantIconCamera from './AssistantIconCamera.vue'
import AssistantIconClose from './AssistantIconClose.vue'
import AssistantIconPencil from './AssistantIconPencil.vue'
import AssistantIconPlus from './AssistantIconPlus.vue'
import AssistantIconSend from './AssistantIconSend.vue'

const props: AssistantIconProps = defineProps({
  name: {
    type: String as PropType<AssistantIconName>,
    required: true,
  },
})

const GLYPHS: Record<AssistantIconName, Component> = {
  camera: AssistantIconCamera,
  calendar: AssistantIconCalendar,
  close: AssistantIconClose,
  send: AssistantIconSend,
  pencil: AssistantIconPencil,
  plus: AssistantIconPlus,
}
</script>

<style scoped>
.assistant-icon {
  display: block;
  width: 1em;
  height: 1em;
  flex: none;
}
</style>
