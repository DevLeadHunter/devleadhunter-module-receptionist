<template>
  <component :is="GLYPHS[props.name]" class="assistant-icon" />
</template>

<script lang="ts" setup>
import type { Component, PropType } from 'vue'
import type { AssistantIconName, AssistantIconProps } from '~/types/AssistantIcon'
import AssistantIconCalendar from '~/components/AssistantIconCalendar.vue'
import AssistantIconCamera from '~/components/AssistantIconCamera.vue'
import AssistantIconClose from '~/components/AssistantIconClose.vue'
import AssistantIconPencil from '~/components/AssistantIconPencil.vue'
import AssistantIconSend from '~/components/AssistantIconSend.vue'

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
