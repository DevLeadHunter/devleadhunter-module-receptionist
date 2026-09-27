<template>
  <button type="button" class="cs-lea" :class="{ 'cs-lea--compact': props.compact }" @click="emit('select')">
    <span class="cs-lea__face">
      <AssistantAvatar :url="props.portraitUrl" :fallback-url="props.portraitFallbackUrl" :alt="props.name" />
      <i class="cs-lea__dot" aria-hidden="true" />
    </span>
    <span class="cs-lea__body">
      <span class="cs-lea__name">{{ props.name }}</span>
      <span class="cs-lea__status"
        ><b>{{ props.statusStrong }}</b> {{ props.statusText }}</span
      >
    </span>
    <ClientSpaceIcon v-if="!props.compact" name="chevron-right" class="cs-lea__chevron" />
  </button>
</template>

<script lang="ts" setup>
import type { EmitFn } from 'vue'
import type { ClientSpaceAssistantLineEmits, ClientSpaceAssistantLineProps } from '~/types/ClientSpaceAssistantLine'

/**
 * The receptionist as the client sees her everywhere: portrait ringed with the business's colour, the green dot
 * of the widget, her name and what she is doing. Tapping opens her settings.
 * @param name The receptionist's first name, or a longer title (« Léa, votre réceptionniste »).
 * @param portraitUrl Her photo.
 * @param portraitFallbackUrl The bust drawn when the photo is missing.
 * @param statusStrong The status's first words, in green.
 * @param statusText The rest of the status.
 * @param compact The sidebar's smaller variant, without the chevron.
 */
const props: ClientSpaceAssistantLineProps = defineProps({
  name: { type: String, required: true },
  portraitUrl: { type: String, required: true },
  portraitFallbackUrl: { type: String, required: true },
  statusStrong: { type: String, required: true },
  statusText: { type: String, required: true },
  compact: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceAssistantLineEmits> = defineEmits<ClientSpaceAssistantLineEmits>()
</script>

<style scoped>
.cs-lea {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  border: 0;
  border-top: 1px solid var(--cs-line);
  border-bottom: 1px solid var(--cs-line);
  background: var(--cs-card);
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.cs-lea--compact {
  padding: 8px 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
}

.cs-lea--compact:hover {
  background: var(--cs-bg);
}

.cs-lea__face {
  position: relative;
  display: block;
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--cs-accent);
}

.cs-lea--compact .cs-lea__face {
  width: 36px;
  height: 36px;
}

.cs-lea__dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--cs-online);
  box-shadow: 0 0 0 2px var(--cs-card);
}

.cs-lea__body {
  display: grid;
  flex: 1;
  min-width: 0;
  line-height: 1.3;
}

.cs-lea__name {
  font-size: 16px;
  font-weight: 600;
}

.cs-lea--compact .cs-lea__name {
  font-size: 14.5px;
}

.cs-lea__status {
  font-size: 13px;
  color: var(--cs-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cs-lea__status b {
  font-weight: 600;
  color: var(--cs-green);
}

.cs-lea__chevron {
  color: var(--cs-faint);
}
</style>
