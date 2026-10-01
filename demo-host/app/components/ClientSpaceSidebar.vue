<template>
  <aside class="cs-side">
    <div class="cs-side__brand">
      <span class="cs-side__logo" aria-hidden="true">{{ businessInitials }}</span>
      <span class="cs-side__brand-text">
        <span class="cs-side__name">{{ props.businessName }}</span>
        <span class="cs-side__kind">Espace client</span>
      </span>
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

    <div class="cs-side__foot">
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
      <button type="button" class="cs-side__item cs-side__item--quiet" @click="emit('open-help')">
        <ClientSpaceIcon name="help-circle" />
        <span>Aide</span>
      </button>
    </div>
  </aside>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type { ClientSpaceSection } from '~/types/ClientSpaceNavigation'
import type { ClientSpaceSidebarEmits, ClientSpaceSidebarProps } from '~/types/ClientSpaceSidebar'
import { CLIENT_SPACE_NAV_ITEMS } from '~/constants/ClientSpaceNavItems'
import { ClientSpaceRequestUtils } from '~/utils/ClientSpaceRequestUtils'

/**
 * The left column of the client space on a wide screen, like the business tools the client already uses: the
 * business with its initials on its colour, the four sections, then the receptionist and the help entry at the
 * bottom. Same entries as the phone's tab bar.
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

const businessInitials: ComputedRef<string> = computed((): string =>
  ClientSpaceRequestUtils.initials(props.businessName),
)
</script>

<style scoped>
.cs-side {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100dvh;
  padding: 16px 12px;
  background: var(--cs-card);
  border-right: 1px solid var(--cs-line);
}

.cs-side__brand {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 44px;
  margin: 0 0 18px;
  padding: 0 6px;
}

.cs-side__logo {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: none;
  border-radius: 10px;
  background: var(--cs-accent-strong);
  color: var(--cs-on-accent);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.cs-side__brand-text {
  display: grid;
  min-width: 0;
  line-height: 1.25;
}

.cs-side__name {
  font-size: 14.5px;
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cs-side__kind {
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
  gap: 11px;
  width: 100%;
  min-height: 40px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--cs-dim);
  text-align: left;
  cursor: pointer;
  transition:
    background-color 150ms ease,
    color 150ms ease;
}

.cs-side__item .cs-icon {
  width: 18px;
  height: 18px;
}

.cs-side__item:hover {
  background: var(--cs-surface-2);
  color: var(--cs-ink);
}

.cs-side__item:focus-visible {
  outline: 2px solid var(--cs-accent-strong);
  outline-offset: 1px;
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

.cs-side__foot {
  display: grid;
  gap: 4px;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--cs-line);
}

.cs-side__label {
  margin: 4px 0 2px;
  padding: 0 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--cs-faint);
}
</style>
