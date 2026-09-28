import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type {
  AssistantAppointmentLabels,
  AssistantAppointmentTime,
  AssistantCapturedContact,
  AssistantLeadReply,
  AssistantSlotRefusalCode,
  AssistantThreadMessage,
} from '~/types/AiAssistant'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantContactDetails } from '~/types/AssistantChatContactForm'
import type { AssistantContactPrefill } from '~/types/AssistantContactPrefill'
import type { AssistantThreadContext } from '~/types/AssistantThread'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import type { UseAssistantLeadFormReturn } from '~/types/UseAssistantLeadForm'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { APPOINTMENT_LABELS, LEAD_LABELS } from '~/constants/AssistantWidgetLabels'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantRequestUtils } from '~/utils/AssistantRequestUtils'
import { AssistantScheduleUtils } from '~/utils/AssistantScheduleUtils'
import { AssistantThreadUtils } from '~/utils/AssistantThreadUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { VisitorContactUtils } from '~/utils/VisitorContactUtils'

/** The refusals of a pick the widget answers by offering the slots again. */
const SLOT_REFUSAL_CODES: string[] = ['slot_taken', 'slot_withdrawn']

/** The visitor's words the business's side of the demo shows for a request left in the chat, at most. */
const CHAT_NEED_MAX_CHARS: number = 140

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
    VisitorContactUtils.extract(AssistantThreadUtils.conversationOf(context.messages.value)),
  )

  /** Show the contact form for a call back: an appointment picked before is not part of it. */
  function openLeadForm(): void {
    if (context.isAssistantUnavailable.value) return
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
      name: details.name,
      contact: details.contact,
      need: details.need,
      kind: hasAppointment ? 'appointment' : photo.hasSentPhoto.value ? 'quote' : 'question',
      slots,
      booked: reply.booked_start !== null,
      hasPhoto: photo.hasSentPhoto.value,
    }
  }

  /**
   * The visitor's own words for a request left in the chat: what their photo shows, else their first question.
   * @returns The need, short enough for an SMS preview; empty when they only gave their number.
   */
  function chatNeed(): string {
    if (photo.leadNeedPrefill.value) return photo.leadNeedPrefill.value
    const firstQuestion: AssistantThreadMessage | undefined = AssistantThreadUtils.conversationOf(
      context.messages.value,
    ).find((message: AssistantThreadMessage): boolean => message.role === 'user')
    const words: string = firstQuestion?.content.trim() ?? ''
    return words.length > CHAT_NEED_MAX_CHARS ? `${words.slice(0, CHAT_NEED_MAX_CHARS - 1).trimEnd()}…` : words
  }

  /**
   * Confirm, as the form does, the request the API filed from a phone number or an email typed in the chat.
   * @param captured - The name and contact the request carries.
   */
  function confirmCapturedContact(captured: AssistantCapturedContact): void {
    if (context.hasSentLead.value) return
    context.hasSentLead.value = true
    captureDemoEvent('assistant_lead_submitted', { source: 'chat' })
    if (context.openPanel.value === 'lead-form') context.openPanel.value = null
    context.pushLocalLine(LEAD_LABELS[context.language.value].sent)
    lastLeadSummary.value = {
      name: captured.name,
      contact: captured.contact,
      need: chatNeed(),
      kind: photo.hasSentPhoto.value ? 'quote' : 'question',
      slots: '',
      booked: false,
      hasPhoto: photo.hasSentPhoto.value,
    }
  }

  /**
   * Whether a refusal code is one of a pick the API refused.
   * @param code - The code the API sent, or null.
   * @returns True for a slot taken or withdrawn meanwhile.
   */
  function isSlotRefusal(code: string | null): code is AssistantSlotRefusalCode {
    return code !== null && SLOT_REFUSAL_CODES.includes(code)
  }

  /**
   * Tell the visitor why their details did not go: a pick taken meanwhile, a sentence written for them, or a failure.
   * @param error - What the call threw.
   * @returns A promise resolved once the slots are offered again, when that is the answer.
   */
  async function reportLeadFailure(error: unknown): Promise<void> {
    const code: string | null = ApiRefusalUtils.code(error)
    const detail: string | null = ApiRefusalUtils.detail(error)
    if (ApiRefusalUtils.status(error) === 409 && isSlotRefusal(code)) await booking.offerSlotsAgain(code)
    else if (ApiRefusalUtils.status(error) === 422 && detail !== null) context.pushLocalLine(detail)
    else context.reportFailure(AssistantRequestUtils.failureOf(error))
  }

  /**
   * Send the visitor's details: the API turns them into a request tied to this conversation.
   * @param details - The name, contact and need typed.
   * @returns A promise resolved once the request is sent.
   */
  async function submitLead(details: AssistantContactDetails): Promise<void> {
    const name: string = details.name.trim()
    const contact: string = details.contact.trim()
    if (isSubmittingLead.value || !name || !VisitorContactUtils.isReachable(contact)) return
    isSubmittingLead.value = true
    const bookedTime: AssistantAppointmentTime | null =
      booking.bookingMode.value === 'calendar' ? booking.chosenTime.value : null
    const sentDetails: AssistantContactDetails = { name, contact, need: details.need.trim() }
    try {
      const reply: AssistantLeadReply = await AssistantRequestUtils.sendLead(context.publicEndpoint, {
        ...sentDetails,
        language: context.language.value,
        session_id: context.sessionId.value,
        internal: DemoBeaconUtils.isInternalVisit(),
        slots: bookedTime ? [] : booking.chosenSlots.value,
        booking: bookedTime ? { start: bookedTime.start, type: booking.chosenKind.value } : null,
      })
      context.hasSentLead.value = true
      captureDemoEvent('assistant_lead_submitted', { source: 'form' })
      context.openPanel.value = null
      context.pushLocalLine(leadConfirmation(reply, bookedTime))
      lastLeadSummary.value = leadSummary(sentDetails, reply, bookedTime)
    } catch (error: unknown) {
      await reportLeadFailure(error)
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
    confirmCapturedContact,
  }
}
