<template>
  <AssistantChatCard
    ref="card"
    :title="props.bookingMode === 'calendar' ? labels.titleCalendar : labels.title"
    :primary-label="labels.next"
    :primary-disabled="!props.canContinue"
    :secondary-label="LEAD_LABELS[props.lang].cancel"
    tabindex="-1"
    @primary="emit('confirm')"
    @secondary="emit('cancel')"
  >
    <p v-if="props.slotsState === 'loading'" class="ai-slots__note">{{ labels.loading }}</p>
    <p v-else-if="props.slotsState === 'error'" class="ai-slots__note">{{ labels.error }}</p>
    <template v-else-if="props.bookingMode === 'calendar'">
      <div v-if="props.kinds.length > 0" class="ai-slots__kinds" role="group" :aria-label="labels.kind">
        <span class="ai-slots__label">{{ labels.kind }}</span>
        <button
          v-for="kind in props.kinds"
          :key="kind"
          type="button"
          class="ai-slots__chip"
          :aria-pressed="props.chosenKind === kind"
          @click="emit('choose-kind', kind)"
        >
          {{ kind }}
        </button>
      </div>
      <p v-if="props.times.length === 0" class="ai-slots__note">{{ labels.none }}</p>
      <ul v-else class="ai-slots__list">
        <li v-for="time in props.times" :key="time.start">
          <button
            type="button"
            class="ai-slots__time"
            :aria-pressed="props.chosenTime?.start === time.start"
            @click="emit('choose-time', time)"
          >
            {{ AssistantScheduleUtils.timeLabel(time.start, props.lang) }}
          </button>
        </li>
      </ul>
      <div class="ai-slots__pages">
        <button v-if="props.hasPreviousPage" type="button" class="ai-slots__more" @click="emit('first-page')">
          {{ labels.first }}
        </button>
        <button v-if="props.hasMoreTimes" type="button" class="ai-slots__more" @click="emit('more')">
          {{ labels.more }}
        </button>
      </div>
    </template>
    <p v-else-if="props.days.length === 0" class="ai-slots__note">{{ labels.none }}</p>
    <ul v-else class="ai-slots__days">
      <li v-for="day in props.days" :key="day.date" class="ai-slots__day">
        <span class="ai-slots__date">{{ AssistantScheduleUtils.dayLabel(day.date, props.lang) }}</span>
        <button
          v-for="period in DAY_PERIODS"
          :key="period"
          type="button"
          class="ai-slots__slot"
          :disabled="!day.periods.includes(period)"
          :aria-pressed="isChosen(day.date, period)"
          :aria-label="AssistantScheduleUtils.slotLabel({ date: day.date, period }, props.lang)"
          @click="emit('toggle-slot', day.date, period)"
        >
          {{ labels.periods[period] }}
        </button>
      </li>
    </ul>
  </AssistantChatCard>
</template>

<script lang="ts" setup>
import type { ComponentPublicInstance, ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref } from 'vue'
import type {
  AssistantAppointmentDay,
  AssistantAppointmentLabels,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantDayPeriod,
  AssistantSlotChoice,
  AssistantSlotsState,
  AssistantWidgetLang,
} from '~/types/AiAssistant'
import type { AssistantChatSlotsCardEmits, AssistantChatSlotsCardProps } from '~/types/AssistantChatSlotsCard'
import { APPOINTMENT_LABELS, LEAD_LABELS } from '~/constants/AssistantWidgetLabels'
import { AssistantScheduleUtils } from '~/utils/AssistantScheduleUtils'

const DAY_PERIODS: AssistantDayPeriod[] = ['morning', 'afternoon']

const props: AssistantChatSlotsCardProps = defineProps({
  lang: {
    type: String as PropType<AssistantWidgetLang>,
    required: true,
  },
  bookingMode: {
    type: String as PropType<AssistantBookingMode>,
    required: true,
  },
  slotsState: {
    type: String as PropType<AssistantSlotsState>,
    required: true,
  },
  days: {
    type: Array as PropType<AssistantAppointmentDay[]>,
    required: true,
  },
  times: {
    type: Array as PropType<AssistantAppointmentTime[]>,
    required: true,
  },
  hasMoreTimes: {
    type: Boolean,
    default: false,
  },
  hasPreviousPage: {
    type: Boolean,
    default: false,
  },
  kinds: {
    type: Array as PropType<string[]>,
    required: true,
  },
  chosenSlots: {
    type: Array as PropType<AssistantSlotChoice[]>,
    required: true,
  },
  chosenTime: {
    type: Object as PropType<AssistantAppointmentTime | null>,
    default: null,
  },
  chosenKind: {
    type: String as PropType<string | null>,
    default: null,
  },
  canContinue: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<AssistantChatSlotsCardEmits> = defineEmits<AssistantChatSlotsCardEmits>()

const card: Ref<ComponentPublicInstance | null> = ref(null)

const labels: ComputedRef<AssistantAppointmentLabels> = computed(
  (): AssistantAppointmentLabels => APPOINTMENT_LABELS[props.lang],
)

/**
 * Whether a half-day is among the visitor's picks.
 * @param date - The ISO day.
 * @param period - The half-day.
 * @returns True when picked.
 */
function isChosen(date: string, period: AssistantDayPeriod): boolean {
  return props.chosenSlots.some((slot: AssistantSlotChoice): boolean => slot.date === date && slot.period === period)
}

/** Move the keyboard focus into the card once the chip that opened it has gone. */
function focus(): void {
  const element: unknown = card.value?.$el
  if (element instanceof HTMLElement) element.focus()
}

defineExpose({ focus })
</script>

<style scoped>
.ai-slots__note {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--ai-ink-dim);
}
.ai-slots__days,
.ai-slots__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ai-slots__day {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 6px;
}
.ai-slots__date,
.ai-slots__label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--ai-ink);
}
.ai-slots__slot,
.ai-slots__chip {
  border: 1px solid var(--ai-line);
  background: var(--ai-paper-2);
  color: var(--ai-ink);
  font: inherit;
  font-size: 0.78rem;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
}
.ai-slots__slot[aria-pressed='true'],
.ai-slots__chip[aria-pressed='true'] {
  border-color: var(--ai-accent-strong);
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
}
.ai-slots__slot:disabled {
  opacity: 0.35;
  cursor: default;
}
.ai-slots__kinds {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.ai-slots__time {
  width: 100%;
  border: 1px solid var(--ai-line);
  background: var(--ai-paper-2);
  color: var(--ai-ink);
  font: inherit;
  font-size: 0.85rem;
  text-align: left;
  padding: 9px 12px;
  border-radius: 12px;
  cursor: pointer;
}
.ai-slots__time[aria-pressed='true'] {
  border-color: var(--ai-accent-strong);
  background: var(--ai-accent-strong);
  color: var(--ai-on-strong);
}
.ai-slots__pages {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}
.ai-slots__more {
  align-self: flex-start;
  border: 0;
  background: none;
  color: var(--ai-ink);
  font: inherit;
  font-size: 0.8rem;
  text-decoration: underline;
  text-underline-offset: 3px;
  padding: 9px 0;
  cursor: pointer;
}
</style>
