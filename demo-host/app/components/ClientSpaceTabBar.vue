<template>
  <nav class="cs-tabs" aria-label="Rubriques">
    <button
      v-for="item in CLIENT_SPACE_NAV_ITEMS"
      :key="item.section"
      type="button"
      class="cs-tabs__item"
      :aria-current="item.section === props.section ? 'page' : undefined"
      @click="emit('navigate', item.section)"
    >
      <ClientSpaceIcon :name="item.icon" />
      {{ item.label }}
      <b v-if="item.section === 'requests' && props.pendingCount > 0" class="cs-tabs__count">{{
        props.pendingCount
      }}</b>
    </button>
  </nav>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { ClientSpaceSection } from '~/types/ClientSpaceNavigation'
import type { ClientSpaceTabBarEmits, ClientSpaceTabBarProps } from '~/types/ClientSpaceTabBar'
import { CLIENT_SPACE_NAV_ITEMS } from '~/constants/ClientSpaceNavItems'

/**
 * The four sections at the bottom of the phone screen, the current one in the business's colour, the count of
 * requests waiting on the Demandes tab.
 * @param section The current section.
 * @param pendingCount How many requests wait for a call back.
 */
const props: ClientSpaceTabBarProps = defineProps({
  section: { type: String as PropType<ClientSpaceSection>, required: true },
  pendingCount: { type: Number, required: true },
})

const emit: EmitFn<ClientSpaceTabBarEmits> = defineEmits<ClientSpaceTabBarEmits>()
</script>

<style scoped>
.cs-tabs {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 6px 4px calc(8px + env(safe-area-inset-bottom, 0px));
  background: var(--cs-card);
  border-top: 1px solid var(--cs-line);
}

.cs-tabs__item {
  position: relative;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 3px;
  min-height: 48px;
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 11px;
  font-weight: 500;
  color: var(--cs-faint);
  cursor: pointer;
}

.cs-tabs__item[aria-current='page'] {
  color: var(--cs-accent-text);
  font-weight: 600;
}

.cs-tabs__item :deep(.cs-icon) {
  width: 24px;
  height: 24px;
}

.cs-tabs__count {
  position: absolute;
  top: 0;
  left: calc(50% + 6px);
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: var(--cs-red);
}
</style>
