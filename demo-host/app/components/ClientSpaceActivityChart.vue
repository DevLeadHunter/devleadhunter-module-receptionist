<template>
  <figure class="cs-chart">
    <figcaption class="cs-chart__legend">
      <span class="cs-chart__key">
        <i class="cs-chart__swatch cs-chart__swatch--conversations" aria-hidden="true" />Conversations
        <b>{{ totalConversations }}</b>
      </span>
      <span class="cs-chart__key">
        <i class="cs-chart__swatch cs-chart__swatch--requests" aria-hidden="true" />Demandes
        <b>{{ totalRequests }}</b>
      </span>
    </figcaption>

    <div class="cs-chart__plot" role="img" :aria-label="summary">
      <div class="cs-chart__scale" aria-hidden="true">
        <span v-for="tick in ticks" :key="tick" class="cs-chart__tick">{{ tick }}</span>
      </div>
      <div class="cs-chart__area">
        <span v-for="tick in ticks" :key="tick" class="cs-chart__line" aria-hidden="true" />
        <div class="cs-chart__days">
          <span v-for="column in columns" :key="column.day" class="cs-chart__day" :title="column.tooltip">
            <i class="cs-chart__bar cs-chart__bar--conversations" :style="{ height: column.conversationsHeight }" />
            <i class="cs-chart__bar cs-chart__bar--requests" :style="{ height: column.requestsHeight }" />
          </span>
        </div>
        <p v-if="isEmpty" class="cs-chart__empty">Pas encore d’activité sur ces {{ props.days.length }} jours.</p>
      </div>
    </div>

    <div class="cs-chart__axis" aria-hidden="true">
      <span v-for="column in columns" :key="column.day" class="cs-chart__date">
        <span v-if="column.axisLabel" :class="`cs-chart__date-text cs-chart__date-text--${column.axisAlign}`">{{
          column.axisLabel
        }}</span>
      </span>
    </div>
  </figure>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientActivityDay } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceActivityChartColumn, ClientSpaceActivityChartProps } from '~/types/ClientSpaceActivityChart'

/** A date under the axis every this many days, and under the last one. */
const AXIS_LABEL_EVERY_DAYS: number = 7

/** The scale's top values, an even number so the middle line reads a whole number. */
const SCALE_STEPS: number[] = [2, 4, 6, 8, 10]

/**
 * The activity of the last days: each day's conversations and requests side by side, on one scale, with the
 * period's totals as the legend. A day's figures read in its tooltip.
 * @param days The days to draw, oldest first.
 */
const props: ClientSpaceActivityChartProps = defineProps({
  days: { type: Array as PropType<AiAssistantClientActivityDay[]>, required: true },
})

const totalConversations: ComputedRef<number> = computed((): number =>
  props.days.reduce((sum: number, day: AiAssistantClientActivityDay): number => sum + day.conversations, 0),
)

const totalRequests: ComputedRef<number> = computed((): number =>
  props.days.reduce((sum: number, day: AiAssistantClientActivityDay): number => sum + day.requests, 0),
)

const isEmpty: ComputedRef<boolean> = computed((): boolean => totalConversations.value + totalRequests.value === 0)

/** The top of the scale: the busiest day, rounded up to 2, 4, 6, 8, 10, 20, 40… */
const scaleMax: ComputedRef<number> = computed((): number => {
  const busiest: number = Math.max(
    1,
    ...props.days.map((day: AiAssistantClientActivityDay): number => Math.max(day.conversations, day.requests)),
  )
  let magnitude: number = 1
  while (10 * magnitude < busiest) magnitude *= 10
  const step: number = SCALE_STEPS.find((candidate: number): boolean => candidate * magnitude >= busiest) ?? 10
  return step * magnitude
})

/** The scale's three lines, top first. */
const ticks: ComputedRef<number[]> = computed((): number[] => [scaleMax.value, scaleMax.value / 2, 0])

const summary: ComputedRef<string> = computed(
  (): string =>
    `${totalConversations.value} conversations et ${totalRequests.value} demandes sur les ${props.days.length} derniers jours`,
)

const columns: ComputedRef<ClientSpaceActivityChartColumn[]> = computed((): ClientSpaceActivityChartColumn[] => {
  const lastIndex: number = props.days.length - 1
  return props.days.map((day: AiAssistantClientActivityDay, index: number): ClientSpaceActivityChartColumn => {
    const dateLabel: string = shortDate(day.day)
    const isLabelled: boolean = index === lastIndex || (index % AXIS_LABEL_EVERY_DAYS === 0 && lastIndex - index > 3)
    return {
      day: day.day,
      conversationsHeight: heightOf(day.conversations),
      requestsHeight: heightOf(day.requests),
      tooltip: `${dateLabel} : ${countLabel(day.conversations, 'conversation')}, ${countLabel(day.requests, 'demande')}`,
      axisLabel: isLabelled ? dateLabel : '',
      axisAlign: index === 0 ? 'start' : index === lastIndex ? 'end' : 'center',
    }
  })
})

/**
 * A bar's height on the scale (an empty day keeps a sliver, so the day still reads).
 * @param value The day's count.
 * @returns The height, in % of the plot.
 */
function heightOf(value: number): string {
  return value === 0 ? '0' : `${Math.max(3, (100 * value) / scaleMax.value)}%`
}

/**
 * A day as the axis reads it.
 * @param day The day, « 2026-09-29 ».
 * @returns « 29 sept. ».
 */
function shortDate(day: string): string {
  const [year, month, date]: number[] = day.split('-').map(Number)
  return new Date(year ?? 1970, (month ?? 1) - 1, date ?? 1).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
  })
}

/**
 * A count with its noun, singular or plural.
 * @param count The count.
 * @param noun The singular noun.
 * @returns « 1 demande », « 3 demandes ».
 */
function countLabel(count: number, noun: string): string {
  return `${count} ${noun}${count > 1 ? 's' : ''}`
}
</script>

<style scoped>
.cs-chart {
  display: grid;
  grid-template-rows: auto minmax(168px, 1fr) auto;
  gap: 12px;
  margin: 0;
  padding: 16px;
}

.cs-chart__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  font-size: 13px;
  color: var(--cs-dim);
}

.cs-chart__key {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.cs-chart__key b {
  font-weight: 650;
  color: var(--cs-ink);
  font-variant-numeric: tabular-nums;
}

.cs-chart__swatch {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.cs-chart__swatch--conversations,
.cs-chart__bar--conversations {
  background: var(--cs-accent-tint);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--cs-accent-strong) 22%, transparent);
}

.cs-chart__swatch--requests,
.cs-chart__bar--requests {
  background: var(--cs-accent-strong);
}

.cs-chart__plot {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
}

.cs-chart__scale {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding-right: 8px;
  font-size: 11px;
  line-height: 1;
  color: var(--cs-faint);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.cs-chart__tick:first-child {
  margin-top: -5px;
}

.cs-chart__tick:last-child {
  margin-bottom: -5px;
}

.cs-chart__area {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.cs-chart__line {
  display: block;
  height: 0;
  border-top: 1px dashed var(--cs-line);
}

.cs-chart__line:last-of-type {
  border-top-style: solid;
}

.cs-chart__days {
  position: absolute;
  inset: 0;
  display: flex;
  gap: 2px;
}

.cs-chart__day {
  display: flex;
  flex: 1;
  align-items: flex-end;
  justify-content: center;
  gap: 1px;
  min-width: 0;
  border-radius: 4px;
}

.cs-chart__day:hover {
  background: var(--cs-surface-2);
}

.cs-chart__bar {
  display: block;
  width: 38%;
  max-width: 9px;
  border-radius: 3px 3px 0 0;
}

.cs-chart__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  font-size: 13.5px;
  color: var(--cs-dim);
}

.cs-chart__axis {
  display: flex;
  gap: 2px;
  margin-left: 28px;
  height: 14px;
  font-size: 11.5px;
  color: var(--cs-faint);
}

.cs-chart__date {
  position: relative;
  flex: 1;
  min-width: 0;
}

.cs-chart__date-text {
  position: absolute;
  top: 0;
  white-space: nowrap;
}

.cs-chart__date-text--start {
  left: 0;
}

.cs-chart__date-text--center {
  left: 50%;
  transform: translateX(-50%);
}

.cs-chart__date-text--end {
  right: 0;
}
</style>
