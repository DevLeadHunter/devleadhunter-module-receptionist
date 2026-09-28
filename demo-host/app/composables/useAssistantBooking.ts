import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type {
  AssistantAppointmentDay,
  AssistantAppointmentLabels,
  AssistantAppointmentSlots,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantDayPeriod,
  AssistantSlotChoice,
  AssistantSlotsState,
} from '~/types/AiAssistant'
import type { AssistantThreadContext } from '~/types/AssistantThread'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import { APPOINTMENT_LABELS } from '~/constants/AssistantWidgetLabels'
import { ASSISTANT_SLOTS_MAX_CHOSEN } from '~/constants/AssistantWidgetLimits'
import { AssistantScheduleUtils } from '~/utils/AssistantScheduleUtils'

/**
 * The appointment panel of a conversation: the agenda's free slots or the open half-days, and the visitor's picks.
 * @param context - The state the conversation's parts share.
 * @returns The offer, the picks and the panel's actions.
 */
export function useAssistantBooking(context: AssistantThreadContext): UseAssistantBookingReturn {
  const bookingMode: Ref<AssistantBookingMode> = ref('request')
  const slotsState: Ref<AssistantSlotsState> = ref('idle')
  const slotDays: Ref<AssistantAppointmentDay[]> = ref([])
  const slotTimes: Ref<AssistantAppointmentTime[]> = ref([])
  const hasMoreTimes: Ref<boolean> = ref(false)
  /** The last slot of the page before (null on the first page of free slots). */
  const slotsAfter: Ref<string | null> = ref(null)
  const maxChosenSlots: Ref<number> = ref(ASSISTANT_SLOTS_MAX_CHOSEN)
  const appointmentKinds: Ref<string[]> = ref([])
  const chosenSlots: Ref<AssistantSlotChoice[]> = ref([])
  const chosenTime: Ref<AssistantAppointmentTime | null> = ref(null)
  const chosenKind: Ref<string | null> = ref(null)
  /** The slot panel opens by itself at most once per visit, when the visitor asks the chat for an appointment. */
  const hasOfferedBooking: Ref<boolean> = ref(false)

  const isSlotPanelOpen: ComputedRef<boolean> = computed((): boolean => context.openPanel.value === 'slots')
  const hasPreviousSlotsPage: ComputedRef<boolean> = computed((): boolean => slotsAfter.value !== null)
  const chosenSlotsLine: ComputedRef<string> = computed((): string =>
    AssistantScheduleUtils.slotsLine(chosenSlots.value, context.language.value),
  )
  const chosenTimeLine: ComputedRef<string> = computed((): string => {
    if (!chosenTime.value) return ''
    const when: string = AssistantScheduleUtils.timeLabel(chosenTime.value.start, context.language.value)
    return chosenKind.value ? `${when} (${chosenKind.value})` : when
  })
  const canContinueBooking: ComputedRef<boolean> = computed((): boolean =>
    bookingMode.value === 'calendar'
      ? chosenTime.value !== null && (appointmentKinds.value.length === 0 || chosenKind.value !== null)
      : chosenSlots.value.length > 0,
  )
  const pickedSummary: ComputedRef<string> = computed((): string => {
    const labels: AssistantAppointmentLabels = APPOINTMENT_LABELS[context.language.value]
    if (chosenSlots.value.length > 0) return `${labels.chosen} : ${chosenSlotsLine.value}`
    if (chosenTime.value) return `${labels.appointment} : ${chosenTimeLine.value}`
    return ''
  })

  /** Forget the half-days, the free slot and the kind picked. */
  function forgetPicks(): void {
    chosenSlots.value = []
    chosenTime.value = null
    chosenKind.value = null
  }

  /**
   * Fetch what the appointment panel offers.
   * @param after - The last free slot shown, to get the next ones (agenda only).
   * @returns A promise resolved once loaded or failed.
   */
  async function loadSlots(after: string | null = null): Promise<void> {
    slotsState.value = 'loading'
    // A new page of slots: a time picked on the page before would stay chosen while out of sight.
    chosenTime.value = null
    try {
      const offer: AssistantAppointmentSlots = await $fetch<AssistantAppointmentSlots>(
        `${context.publicEndpoint}/appointment-slots`,
        { query: after ? { after } : {} },
      )
      bookingMode.value = offer.mode
      slotsAfter.value = after
      slotDays.value = offer.days
      maxChosenSlots.value = offer.max_chosen
      slotTimes.value = offer.times
      hasMoreTimes.value = offer.has_more
      appointmentKinds.value = offer.types
      if (chosenKind.value !== null && !offer.types.includes(chosenKind.value)) chosenKind.value = null
      slotsState.value = 'ready'
    } catch {
      slotsState.value = 'error'
    }
  }

  /**
   * Show the appointment panel and load what it offers: the agenda's free slots, or open half-days.
   * @returns A promise resolved once the offer is shown (or its failure).
   */
  async function openSlotPanel(): Promise<void> {
    if (context.isBusy.value || context.hasSentLead.value) return
    context.noteInlineOpening()
    hasOfferedBooking.value = true
    context.openPanel.value = 'slots'
    // Free slots change: the agenda's are read again, from the first page, at each opening.
    if (slotsState.value !== 'ready' || bookingMode.value === 'calendar') await loadSlots()
  }

  /** Close the appointment panel and forget the picks. */
  function closeSlotPanel(): void {
    if (context.openPanel.value === 'slots') context.openPanel.value = null
    forgetPicks()
  }

  /**
   * Show the first page of free slots again.
   * @returns A promise resolved once loaded.
   */
  async function loadFirstSlotsPage(): Promise<void> {
    await loadSlots(null)
  }

  /**
   * Replace the free slots shown by the next ones.
   * @returns A promise resolved once they are loaded.
   */
  async function showMoreTimes(): Promise<void> {
    const last: AssistantAppointmentTime | undefined = slotTimes.value[slotTimes.value.length - 1]
    if (!last) return
    await loadSlots(last.start)
  }

  /**
   * Pick or drop a half-day; past the maximum, the oldest pick makes room.
   * @param date - The ISO day.
   * @param period - The half-day.
   */
  function toggleSlot(date: string, period: AssistantDayPeriod): void {
    const isPicked: boolean = chosenSlots.value.some(
      (slot: AssistantSlotChoice): boolean => slot.date === date && slot.period === period,
    )
    if (isPicked) {
      chosenSlots.value = chosenSlots.value.filter(
        (slot: AssistantSlotChoice): boolean => slot.date !== date || slot.period !== period,
      )
      return
    }
    chosenSlots.value = [...chosenSlots.value, { date, period }].slice(-maxChosenSlots.value)
  }

  /**
   * Pick a free slot of the agenda.
   * @param time - The slot.
   */
  function chooseTime(time: AssistantAppointmentTime): void {
    chosenTime.value = time
  }

  /**
   * Pick the kind of appointment the agenda offers.
   * @param kind - The kind.
   */
  function chooseKind(kind: string): void {
    chosenKind.value = kind
  }

  /** Move on to the contact form with the picked appointment. */
  function confirmSlots(): void {
    if (!canContinueBooking.value) return
    context.openPanel.value = 'lead-form'
  }

  return {
    bookingMode,
    slotsState,
    slotDays,
    slotTimes,
    hasMoreTimes,
    hasPreviousSlotsPage,
    appointmentKinds,
    chosenSlots,
    chosenTime,
    chosenKind,
    chosenSlotsLine,
    canContinueBooking,
    pickedSummary,
    hasOfferedBooking,
    isSlotPanelOpen,
    loadSlots,
    openSlotPanel,
    closeSlotPanel,
    loadFirstSlotsPage,
    showMoreTimes,
    toggleSlot,
    chooseTime,
    chooseKind,
    confirmSlots,
    forgetPicks,
  }
}
