<template>
  <div class="feed">
    <div class="feed__phone">
      <span class="feed__island" aria-hidden="true" />
      <div class="feed__clock">
        <span class="feed__date">Ce soir, sur votre téléphone</span>
        <span class="feed__time">{{ props.timeLabel }}</span>
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

      <span class="feed__home" aria-hidden="true" />
    </div>

    <p class="feed__hint">{{ props.hintText }}</p>
  </div>
</template>

<script lang="ts" setup>
import type { AssistantDemoOwnerFeedProps } from '~/types/AssistantDemoOwnerFeed'

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
}
.feed__phone {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
  max-width: 340px;
  min-height: 390px;
  margin-inline: auto;
  padding: 50px 14px 14px;
  border: 7px solid #15120e;
  border-radius: 44px;
  background:
    radial-gradient(120% 65% at 50% 0%, color-mix(in srgb, var(--a-accent) 60%, #2a241c) 0%, transparent 72%),
    linear-gradient(180deg, #2a241c 0%, #0f0d0a 100%);
  box-shadow: 0 30px 70px -34px rgba(23, 19, 13, 0.6);
  color: #fff;
}
.feed__island {
  position: absolute;
  top: 12px;
  left: 50%;
  width: 92px;
  height: 26px;
  border-radius: 999px;
  background: #000;
  transform: translateX(-50%);
}
.feed__clock {
  display: grid;
  justify-items: center;
  gap: 4px;
}
.feed__date {
  font-size: 13.5px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.82);
}
.feed__time {
  font-size: 68px;
  font-weight: 650;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}
.feed__notification {
  position: relative;
  display: grid;
  grid-template-columns: 38px 1fr;
  gap: 11px;
  align-items: start;
  padding: 12px 14px 13px 12px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  color: #111;
  box-shadow: 0 18px 40px -22px rgba(0, 0, 0, 0.6);
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
.feed__home {
  align-self: center;
  width: 118px;
  height: 5px;
  margin-top: auto;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
}
.feed__hint {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.5;
  text-align: center;
  color: var(--ia-ink-dim);
}
@media (prefers-reduced-motion: reduce) {
  .feed__notification--new {
    animation: none;
  }
}
</style>
