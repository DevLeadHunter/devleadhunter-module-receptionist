<template>
  <div class="feed">
    <div class="feed__bar">
      <span class="feed__time">{{ props.timeLabel }}</span>
      <span class="feed__where">Sur votre téléphone</span>
    </div>

    <div
      :key="props.arrivalKey"
      class="feed__notification"
      :class="{ 'feed__notification--new': !props.isExample || props.arrivalKey > 0 }"
      aria-live="polite"
    >
      <span class="feed__app" aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path
            d="M12 3C6.5 3 2.5 6.6 2.5 11c0 2.4 1.2 4.6 3.2 6.1L5 21l4.4-2.1c.8.2 1.7.3 2.6.3 5.5 0 9.5-3.6 9.5-8.1S17.5 3 12 3Z"
            fill="#fff"
          />
        </svg>
      </span>
      <div class="feed__body">
        <div class="feed__top">
          <span class="feed__title">{{ props.assistantName }} · réceptionniste</span>
          <span class="feed__when">maintenant</span>
        </div>
        <p class="feed__text">{{ props.alertText }}</p>
      </div>
      <span v-if="props.isExample" class="feed__tag">exemple</span>
    </div>

    <p class="feed__hint">{{ props.hintText }}</p>
  </div>
</template>

<script lang="ts" setup>
import type { AssistantDemoOwnerFeedProps } from '~/types/AssistantDemoOwnerFeed'

/**
 * The business's side of the demo: the SMS its phone receives when a request lands, as a notification card on
 * the page (the visitor's own request replaces the trade's example once they send one).
 */
const props: AssistantDemoOwnerFeedProps = defineProps({
  timeLabel: {
    type: String,
    required: true,
  },
  assistantName: {
    type: String,
    required: true,
  },
  alertText: {
    type: String,
    required: true,
  },
  isExample: {
    type: Boolean,
    default: true,
  },
  hintText: {
    type: String,
    required: true,
  },
  arrivalKey: {
    type: Number,
    default: 0,
  },
})
</script>

<style scoped>
.feed {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--ia-line);
  background: var(--ia-card);
  box-shadow: 0 30px 70px -34px rgba(23, 19, 13, 0.35);
}
.feed__bar {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: var(--ia-ink-dim);
}
.feed__time {
  font-family: var(--ia-font-d);
  font-size: 30px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.02em;
  color: var(--ia-ink);
  font-variant-numeric: tabular-nums;
}
.feed__where {
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 11px;
}
.feed__notification {
  position: relative;
  display: grid;
  grid-template-columns: 38px 1fr;
  gap: 11px;
  align-items: start;
  padding: 12px 14px 13px 12px;
  border-radius: 18px;
  background: #fff;
  color: #111;
  border: 1px solid var(--ia-line-soft);
  box-shadow: 0 18px 40px -22px rgba(23, 19, 13, 0.45);
}
.feed__notification--new {
  animation: feed-drop 0.45s cubic-bezier(0.2, 0.7, 0.3, 1);
}
@keyframes feed-drop {
  from {
    transform: translateY(18px);
    opacity: 0;
  }
  to {
    transform: none;
    opacity: 1;
  }
}
.feed__app {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(180deg, #67e07a, #2fb648);
  display: grid;
  place-items: center;
}
.feed__app svg {
  width: 24px;
  height: 24px;
}
.feed__body {
  min-width: 0;
}
.feed__top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.feed__title {
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: -0.01em;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feed__when {
  flex: none;
  font-size: 12px;
  color: #6b6b6b;
}
.feed__text {
  margin: 2px 0 0;
  font-size: 14.5px;
  line-height: 1.4;
  letter-spacing: -0.01em;
  color: #1c1c1e;
  overflow-wrap: anywhere;
}
.feed__tag {
  position: absolute;
  top: -9px;
  right: 14px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--ia-paper);
  border: 1px solid var(--ia-line);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ia-ink-dim);
}
.feed__hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ia-ink-dim);
}
@media (prefers-reduced-motion: reduce) {
  .feed__notification--new {
    animation: none;
  }
}
</style>
