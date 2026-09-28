import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AssistantAppointmentLabels, AssistantAppointmentTime, AssistantLeadReply } from '~/types/AiAssistant'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantContactDetails } from '~/types/AssistantChatContactForm'
import type { AssistantContactPrefill } from '~/types/AssistantContactPrefill'
import type { AssistantThreadContext } from '~/types/AssistantThread'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import type { UseAssistantLeadFormReturn } from '~/types/UseAssistantLeadForm'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { APPOINTMENT_LABELS, FALLBACK_REPLY, LEAD_LABELS } from '~/constants/AssistantWidgetLabels'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantScheduleUtils } from '~/utils/AssistantScheduleUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { VisitorContactUtils } from '~/utils/VisitorContactUtils'

/**
 * The contact form of a conversation: the visitor's details become a request, with the appointment and the photo.
 * @param context - The state the conversation's parts share.
 * @param booking - The appointment panel (the picks go with the request).
 * @param photo - The photo upload (a request with a photo is a quote).
 * @returns The form's state and actions.
 */
export function useAssistantLeadForm(
  context: AssistantThreadContext,
  booking: UseAssistantBookingReturn,
  photo: UseAssistantPhotoUploadReturn,
): UseAssistantLeadFormReturn {
  const isSubmittingLead: Ref<boolean> = ref(false)
  const lastLeadSummary: Ref<AssistantLeadSummary | null> = ref(null)

  const isLeadFormOpen: ComputedRef<boolean> = computed((): boolean => context.openPanel.value === 'lead-form')
  /** What the visitor already gave in the chat (« Léo », « 06 42 19 38 12 »): the form opens filled with it. */
  const leadPrefill: ComputedRef<AssistantContactPrefill> = computed((): AssistantContactPrefill =>
    VisitorContactUtils.extract(context.messages.value),
  )

  /** Show the contact form for a call back: an appointment picked before is not part of it. */
  function openLeadForm(): void {
    context.noteInlineOpening()
    booking.forgetPicks()
    context.openPanel.value = 'lead-form'
  }

  /** Close the contact form; an appointment's picks go with it. */
  function cancelLeadForm(): void {
    if (context.openPanel.value === 'lead-form') context.openPanel.value = null
    booking.forgetPicks()
  }

  /**
   * What the visitor reads once their details are sent.
   * @param reply - The API's answer.
   * @param bookedTime - The free slot they picked, if any.
   * @returns The booked slot, the half-days (or the slot) the business will confirm, or the call-back promise.
   */
  function leadConfirmation(reply: AssistantLeadReply, bookedTime: AssistantAppointmentTime | null): string {
    const labels: AssistantAppointmentLabels = APPOINTMENT_LABELS[context.language.value]
    if (reply.booked_start) {
      const when: string = AssistantScheduleUtils.timeLabel(reply.booked_start, context.language.value)
      const kind: string | null = booking.chosenKind.value
      const booked: string = labels.booked.replace('{slots}', kind ? `${when} (${kind})` : when)
      if (reply.confirmation_channel === 'sms') return booked + labels.bookedSms
      if (reply.confirmation_channel === 'email') return booked + labels.bookedEmail
      return booked
    }
    if (bookedTime) {
      return labels.sent.replace('{slots}', AssistantScheduleUtils.timeLabel(bookedTime.start, context.language.value))
    }
    if (booking.chosenSlots.value.length > 0) return labels.sent.replace('{slots}', booking.chosenSlotsLine.value)
    return LEAD_LABELS[context.language.value].sent
  }

  /**
   * What the request just sent holds, for the page showing what the business receives.
   * @param details - The details the visitor typed.
   * @param reply - The API's answer.
   * @param bookedTime - The free slot picked, if any.
   * @returns The summary the page can turn into the business's alert.
   */
  function leadSummary(
    details: AssistantContactDetails,
    reply: AssistantLeadReply,
    bookedTime: AssistantAppointmentTime | null,
  ): AssistantLeadSummary {
    const hasAppointment: boolean =
      bookedTime !== null || booking.chosenSlots.value.length > 0 || reply.booked_start !== null
    let slots: string = ''
    if (reply.booked_start) slots = AssistantScheduleUtils.timeLabel(reply.booked_start, context.language.value)
    else if (bookedTime) slots = AssistantScheduleUtils.timeLabel(bookedTime.start, context.language.value)
    else if (booking.chosenSlots.value.length > 0) slots = booking.chosenSlotsLine.value
    return {
      name: details.name.trim(),
      contact: details.contact.trim(),
      need: details.need.trim(),
      kind: hasAppointment ? 'appointment' : photo.hasSentPhoto.value ? 'quote' : 'question',
      slots,
      booked: reply.booked_start !== null,
      hasPhoto: photo.hasSentPhoto.value,
    }
  }

  /**
   * Tell the visitor why their pick was refused, then offer the slots again.
   * @param detail - The API's sentence for the refusal.
   * @returns A promise resolved once the offer is read again.
   */
  async function offerSlotsAgain(detail: string | null): Promise<void> {
    const isWithdrawn: boolean = detail !== null && detail.includes('proposé')
    const labels: AssistantAppointmentLabels = APPOINTMENT_LABELS[context.language.value]
    context.messages.value.push({ role: 'assistant', content: isWithdrawn ? labels.unavailable : labels.taken })
    booking.forgetPicks()
    context.openPanel.value = 'slots'
    await booking.loadSlots()
  }

  /**
   * Send the visitor's details: the API turns them into a request tied to this conversation.
   * @param details - The name, contact and need typed.
   * @returns A promise resolved once the request is sent.
   */
  async function submitLead(details: AssistantContactDetails): Promise<void> {
    if (isSubmittingLead.value || !details.name.trim() || !VisitorContactUtils.isReachable(details.contact)) return
    isSubmittingLead.value = true
    const bookedTime: AssistantAppointmentTime | null =
      booking.bookingMode.value === 'calendar' ? booking.chosenTime.value : null
    try {
      const reply: AssistantLeadReply = await $fetch<AssistantLeadReply>(`${context.publicEndpoint}/lead`, {
        method: 'POST',
        body: {
          name: details.name,
          contact: details.contact,
          need: details.need,
          language: context.language.value,
          session_id: context.sessionId.value,
          internal: DemoBeaconUtils.isInternalVisit(),
          slots: bookedTime ? [] : booking.chosenSlots.value,
          booking: bookedTime ? { start: bookedTime.start, type: booking.chosenKind.value } : null,
        },
      })
      context.hasSentLead.value = true
      captureDemoEvent('assistant_lead_submitted')
      context.openPanel.value = null
      context.messages.value.push({ role: 'assistant', content: leadConfirmation(reply, bookedTime) })
      lastLeadSummary.value = leadSummary(details, reply, bookedTime)
    } catch (error: unknown) {
      // A slot taken or withdrawn meanwhile answers 409: the offer is read again. A 422 carries a sentence
      // written for the visitor (a kind to choose, a test visit); anything else is a technical failure.
      const status: number | undefined = ApiRefusalUtils.status(error)
      const detail: string | null = ApiRefusalUtils.detail(error)
      const hasPick: boolean = bookedTime !== null || booking.chosenSlots.value.length > 0
      if (hasPick && status === 409) await offerSlotsAgain(detail)
      else if (status === 422 && detail !== null) context.messages.value.push({ role: 'assistant', content: detail })
      else context.messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[context.language.value] })
    } finally {
      isSubmittingLead.value = false
    }
  }

  return {
    isLeadFormOpen,
    isSubmittingLead,
    leadPrefill,
    lastLeadSummary,
    openLeadForm,
    cancelLeadForm,
    submitLead,
  }
}
