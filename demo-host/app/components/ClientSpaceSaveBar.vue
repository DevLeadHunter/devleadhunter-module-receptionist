<template>
  <div class="cs-savebar">
    <button type="submit" class="cs-button" :disabled="props.isBusy || !props.canSave">
      {{ props.isBusy ? 'Enregistrement…' : 'Enregistrer' }}
    </button>
    <slot />
    <span v-if="props.errorMessage" class="cs-savebar__error">{{ props.errorMessage }}</span>
    <span v-else-if="props.showSaved" class="cs-savebar__saved">Enregistré.</span>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { ClientSpaceSaveBarProps } from '~/types/ClientSpaceSaveBar'

/**
 * The foot of a client-space form: its submit button, extra buttons (default slot), then the last save's outcome.
 * The button submits the enclosing form, so the browser still checks its fields and Enter in a field still saves.
 * @param isBusy A call is in flight.
 * @param canSave There is something to save.
 * @param errorMessage Why the last call was refused, if it was.
 * @param showSaved The last save went through and nothing changed since.
 */
const props: ClientSpaceSaveBarProps = defineProps({
  isBusy: { type: Boolean, default: false },
  canSave: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  showSaved: { type: Boolean, default: false },
})
</script>

<style scoped>
.cs-savebar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.cs-savebar__error {
  font-size: 13px;
  color: var(--cs-danger);
}

.cs-savebar__saved {
  font-size: 13px;
  color: var(--cs-ink-dim);
}
</style>
