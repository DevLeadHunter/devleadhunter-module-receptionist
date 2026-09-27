<template>
  <aside class="cs-side">
    <div class="cs-side__brand">
      <p class="cs-side__name">{{ props.businessName }}</p>
      <p class="cs-side__kind">Espace client</p>
    </div>

    <nav class="cs-side__nav" aria-label="Rubriques">
      <button
        v-for="item in CLIENT_SPACE_NAV_ITEMS"
        :key="item.section"
        type="button"
        class="cs-side__item"
        :aria-current="item.section === props.section ? 'page' : undefined"
        @click="emit('navigate', item.section)"
      >
        <ClientSpaceIcon :name="item.icon" />
        <span>{{ item.label }}</span>
        <b v-if="item.section === 'requests' && props.pendingCount > 0" class="cs-side__count">{{
          props.pendingCount
        }}</b>
      </button>
    </nav>

    <p class="cs-side__label">Votre réceptionniste</p>
    <ClientSpaceAssistantLine
      :name="props.assistantName"
      :portrait-url="props.portraitUrl"
      :portrait-fallback-url="props.portraitFallbackUrl"
      status-strong="En ligne"
      status-text="répond à vos visiteurs"
      compact
      @select="emit('open-assistant')"
    />

    <div class="cs-side__foot">
      <button type="button" class="cs-side__item cs-side__item--quiet" @click="emit('open-help')">
        <ClientSpaceIcon name="help-circle" />
        <span>Aide</span>
      </button>
    </div>
  </aside>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { ClientSpaceSection } from '~/types/ClientSpaceNavigation'
import type { ClientSpaceSidebarEmits, ClientSpaceSidebarProps } from '~/types/ClientSpaceSidebar'
import { CLIENT_SPACE_NAV_ITEMS } from '~/constants/ClientSpaceNavItems'

/**
 * The left column of the client space on a wide screen: the business, the four sections, the receptionist and
 * the help entry. Same entries as the phone's tab bar, laid out like Qonto's.
 * @param businessName The business.
 * @param section The current section.
 * @param pendingCount How many requests wait for a call back.
 * @param assistantName The receptionist's first name.
 * @param portraitUrl Her photo.
 * @param portraitFallbackUrl The bust drawn when the photo is missing.
 */
const props: ClientSpaceSidebarProps = defineProps({
  businessName: { type: String, required: true },
  section: { type: String as PropType<ClientSpaceSection>, required: true },
  pendingCount: { type: Number, required: true },
  assistantName: { type: String, required: true },
  portraitUrl: { type: String, required: true },
  portraitFallbackUrl: { type: String, required: true },
})

const emit: EmitFn<ClientSpaceSidebarEmits> = defineEmits<ClientSpaceSidebarEmits>()
</script>

<style scoped>
.cs-side {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100dvh;
  padding: 26px 14px 20px;
  background: var(--cs-card);
  border-right: 1px solid var(--cs-line);
}

.cs-side__brand {
  padding: 0 10px 18px;
}

.cs-side__name {
  margin: 0;
  font-family: Fraunces, Georgia, serif;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.15;
}

.cs-side__kind {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--cs-faint);
}

.cs-side__nav {
  display: grid;
  gap: 2px;
}

.cs-side__item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 42px;
  padding: 0 10px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  font: inherit;
  font-size: 14.5px;
  font-weight: 500;
  color: var(--cs-dim);
  text-align: left;
  cursor: pointer;
}

.cs-side__item:hover {
  background: var(--cs-bg);
  color: var(--cs-ink);
}

.cs-side__item[aria-current='page'] {
  background: var(--cs-accent-tint);
  color: var(--cs-accent-text);
  font-weight: 600;
}

.cs-side__item--quiet {
  font-size: 13.5px;
}

.cs-side__count {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: var(--cs-red);
}

.cs-side__label {
  margin: 22px 0 6px;
  padding: 0 10px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--cs-faint);
}

.cs-side__foot {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--cs-line);
}
</style>
