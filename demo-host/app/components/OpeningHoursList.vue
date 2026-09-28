<template>
  <dl class="opening-hours">
    <div
      v-for="row in props.rows"
      :key="row.day"
      class="opening-hours__row"
      :class="{ 'opening-hours__row--today': row.is_today }"
    >
      <dt class="opening-hours__day">
        {{ capitalizeDay(row.day) }}
        <span v-if="row.is_today" class="opening-hours__today">aujourd'hui</span>
      </dt>
      <dd class="opening-hours__hours">{{ row.hours }}</dd>
    </div>
  </dl>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { AiAssistantOpeningHoursRow } from '~/types/AiAssistantPublicBusiness'
import type { OpeningHoursListProps } from '~/types/OpeningHoursList'

const props: OpeningHoursListProps = defineProps({
  rows: { type: Array as PropType<AiAssistantOpeningHoursRow[]>, required: true },
})

/**
 * A day as a line starts it (« lundi » → « Lundi »).
 * @param day - The day, as the listing words it.
 * @returns The day with its first letter in capitals.
 */
function capitalizeDay(day: string): string {
  return day.charAt(0).toLocaleUpperCase('fr-FR') + day.slice(1)
}
</script>

<style scoped>
.opening-hours {
  margin: 0;
  display: grid;
}
.opening-hours__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-block: 7px;
  border-bottom: 1px solid var(--ia-line-soft);
  color: var(--ia-ink-dim);
}
.opening-hours__row:last-child {
  border-bottom: 0;
}
.opening-hours__row--today {
  color: var(--ia-ink);
  font-weight: 600;
}
.opening-hours__day {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.opening-hours__today {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--a-accent-text);
}
.opening-hours__hours {
  margin: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
