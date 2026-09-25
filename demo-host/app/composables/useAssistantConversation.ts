import type { ComputedRef, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type {
  AiAssistantConfig,
  AssistantAppointmentDay,
  AssistantAppointmentLabels,
  AssistantAppointmentSlots,
  AssistantAppointmentTime,
  AssistantBookingMode,
  AssistantChatMessage,
  AssistantChatReply,
  AssistantDayPeriod,
  AssistantLeadReply,
  AssistantPhotoReply,
  AssistantSlotChoice,
  AssistantSlotsState,
  AssistantWidgetLang,
} from '~/types/AiAssistant'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantContactDetails } from '~/types/AssistantChatContactForm'
import type { UseAssistantConversationReturn } from '~/types/UseAssistantConversation'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import {
  APPOINTMENT_LABELS,
  FALLBACK_REPLY,
  GREETING_TEMPLATES,
  LANGUAGE_LABELS,
  LEAD_LABELS,
  PHOTO_LABELS,
  SUGGESTIONS,
} from '~/constants/AssistantWidgetLabels'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantScheduleUtils } from '~/utils/AssistantScheduleUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { PhotoCompressionUtils } from '~/utils/PhotoCompressionUtils'

const DEFAULT_LANG: AssistantWidgetLang = 'fr'

/** Laid out in a page, the greeting is typed before it appears, like a first reply; the panel is on screen already. */
const INLINE_GREETING_DELAY_MS: number = 900

/** A French word starting with a vowel or a mute h takes « d' » (« d'Atelier ») rather than « de ». */
const FRENCH_ELISION_START: RegExp = /^[aeiouyàâäéèêëîïôöùûüh]/i

/** A returning visitor keeps their conversation across page loads, bounded so storage never grows unchecked. */
const MAX_STORED_MESSAGES: number = 40

/** Photos a visitor may send for one quote request (the API enforces the same quota per session). */
const MAX_PHOTOS: number = 3

/**
 * One visitor's conversation with an assistant: thread, language, photo, appointment, contact details and replies.
 * @param config - The assistant's public configuration.
 * @param inline - True when the widget is laid out in a page: its opening then counts at the first interaction.
 * @returns The conversation's state and the actions the widget offers.
 */
export function useAssistantConversation(config: AiAssistantConfig, inline: boolean): UseAssistantConversationReturn {
  const runtimeConfig: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
  const publicEndpoint: string = `${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${config.slug}`
  const storageKey: string = `dlh-assistant-${config.slug}`

  const messages: Ref<AssistantChatMessage[]> = ref([])
  const lang: Ref<AssistantWidgetLang> = ref(DEFAULT_LANG)
  const draft: Ref<string> = ref('')
  const isBusy: Ref<boolean> = ref(false)
  /** Random id sent with every turn so the server journal groups this visitor's conversation. */
  const sessionId: Ref<string> = ref('')
  const photoPreviews: Ref<Record<number, string>> = ref({})
  const photosRemaining: Ref<number> = ref(MAX_PHOTOS)
  const hasSentPhoto: Ref<boolean> = ref(false)
  const isPhotoPanelOpen: Ref<boolean> = ref(false)
  const isSlotPanelOpen: Ref<boolean> = ref(false)
  const showLeadForm: Ref<boolean> = ref(false)
  const leadSent: Ref<boolean> = ref(false)
  const isSubmittingLead: Ref<boolean> = ref(false)
  const leadNeedPrefill: Ref<string> = ref('')
  const bookingMode: Ref<AssistantBookingMode> = ref('request')
  const slotsState: Ref<AssistantSlotsState> = ref('idle')
  const slotDays: Ref<AssistantAppointmentDay[]> = ref([])
  const slotTimes: Ref<AssistantAppointmentTime[]> = ref([])
  const hasMoreTimes: Ref<boolean> = ref(false)
  /** The last slot of the page before (null on the first page of free slots). */
  const slotsAfter: Ref<string | null> = ref(null)
  const maxChosenSlots: Ref<number> = ref(2)
  const appointmentKinds: Ref<string[]> = ref([])
  const chosenSlots: Ref<AssistantSlotChoice[]> = ref([])
  const chosenTime: Ref<AssistantAppointmentTime | null> = ref(null)
  const chosenKind: Ref<string | null> = ref(null)
  /** The slot panel opens by itself at most once per visit, when the visitor asks the chat for an appointment. */
  const hasOfferedBooking: Ref<boolean> = ref(false)
  const hasCapturedInlineOpening: Ref<boolean> = ref(false)
  const lastLeadSummary: Ref<AssistantLeadSummary | null> = ref(null)

  const offeredLanguages: ComputedRef<AssistantWidgetLang[]> = computed((): AssistantWidgetLang[] => {
    const codes: AssistantWidgetLang[] = config.languages.filter(
      (code: string): code is AssistantWidgetLang => code in LANGUAGE_LABELS,
    )
    return codes.length ? codes : [DEFAULT_LANG]
  })
  const suggestions: ComputedRef<string[]> = computed((): string[] => SUGGESTIONS[lang.value])
  const hasPreviousSlotsPage: ComputedRef<boolean> = computed((): boolean => slotsAfter.value !== null)
  const chosenSlotsLine: ComputedRef<string> = computed((): string =>
    AssistantScheduleUtils.slotsLine(chosenSlots.value, lang.value),
  )
  const chosenTimeLine: ComputedRef<string> = computed((): string => {
    if (!chosenTime.value) return ''
    const when: string = AssistantScheduleUtils.timeLabel(chosenTime.value.start, lang.value)
    return chosenKind.value ? `${when} (${chosenKind.value})` : when
  })
  const canContinueBooking: ComputedRef<boolean> = computed((): boolean =>
    bookingMode.value === 'calendar'
      ? chosenTime.value !== null && (appointmentKinds.value.length === 0 || chosenKind.value !== null)
      : chosenSlots.value.length > 0,
  )
  const pickedSummary: ComputedRef<string> = computed((): string => {
    const labels: AssistantAppointmentLabels = APPOINTMENT_LABELS[lang.value]
    if (chosenSlots.value.length > 0) return `${labels.chosen} : ${chosenSlotsLine.value}`
    if (chosenTime.value) return `${labels.appointment} : ${chosenTimeLine.value}`
    return ''
  })
  /** The opening chips show under the greeting only, until the visitor writes or opens a panel. */
  const showChips: ComputedRef<boolean> = computed(
    (): boolean =>
      messages.value.length <= 1 && !isSlotPanelOpen.value && !isPhotoPanelOpen.value && !showLeadForm.value,
  )
  /** A slim way to leave one's details stays above the composer, from the greeting until the request is sent. */
  const showCallbackBar: ComputedRef<boolean> = computed(
    (): boolean => !leadSent.value && !showLeadForm.value && !isSlotPanelOpen.value && !isPhotoPanelOpen.value,
  )

  /**
   * Whether a value is a well-formed chat message (guards against corrupted stored data).
   * @param value - A parsed entry from storage.
   * @returns True when it is a usable message.
   */
  function isChatMessage(value: unknown): value is AssistantChatMessage {
    if (typeof value !== 'object' || value === null) return false
    const entry: Record<string, unknown> = value as Record<string, unknown>
    return (entry.role === 'user' || entry.role === 'assistant') && typeof entry.content === 'string'
  }

  /**
   * Restore this visitor's saved conversation and language for the assistant, when any.
   * @returns True when a previous conversation was restored (so the widget skips the fresh greeting).
   */
  function restoreConversation(): boolean {
    // Inside the try: a browser that refuses storage to a third-party iframe throws on the mere access.
    try {
      const raw: string | null = localStorage.getItem(storageKey)
      if (!raw) return false
      const saved: { lang?: unknown; messages?: unknown; sessionId?: unknown } = JSON.parse(raw)
      if (typeof saved.sessionId === 'string' && saved.sessionId) sessionId.value = saved.sessionId
      if (
        typeof saved.lang === 'string' &&
        offeredLanguages.value.some((code: AssistantWidgetLang): boolean => code === saved.lang)
      ) {
        lang.value = saved.lang as AssistantWidgetLang
      }
      const restored: AssistantChatMessage[] = Array.isArray(saved.messages) ? saved.messages.filter(isChatMessage) : []
      if (!restored.length) return false
      messages.value = restored.slice(-MAX_STORED_MESSAGES)
      return true
    } catch {
      return false
    }
  }

  /** Persist this visitor's conversation and language, bounded to the most recent messages. */
  function persistConversation(): void {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          lang: lang.value,
          sessionId: sessionId.value,
          messages: messages.value.slice(-MAX_STORED_MESSAGES),
        }),
      )
    } catch {
      // Storage unavailable (private mode, third-party iframe) or full: the widget keeps working from memory.
    }
  }

  /**
   * The visitor's browser language, when the assistant offers it.
   * @returns The matching offered language, or null when none of the visitor's languages is offered.
   */
  function detectPreferredLang(): AssistantWidgetLang | null {
    if (typeof navigator === 'undefined') return null
    const offered: AssistantWidgetLang[] = offeredLanguages.value
    const wanted: string[] = [navigator.language, ...(navigator.languages ?? [])]
    for (const raw of wanted) {
      const code: string = raw.slice(0, 2).toLowerCase()
      const match: AssistantWidgetLang | undefined = offered.find(
        (offer: AssistantWidgetLang): boolean => offer === code,
      )
      if (match) return match
    }
    return null
  }

  /**
   * A random id for this visitor's conversation (the browser's UUID when available).
   * @returns The new session id.
   */
  function newSessionId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
  }

  /** Restore a returning visitor's conversation, else open in their browser language when offered. */
  function restore(): void {
    const restored: boolean = restoreConversation()
    if (!restored) {
      const preferred: AssistantWidgetLang | null = detectPreferredLang()
      if (preferred) lang.value = preferred
    }
    if (!sessionId.value) sessionId.value = newSessionId()
  }

  /**
   * The greeting in a language: the persona introduces itself as the business's AI receptionist, then asks.
   * @param code - The language of the greeting.
   * @returns The greeting text.
   */
  function greetingText(code: AssistantWidgetLang): string {
    const business: string = BusinessNameUtils.short(config.business_name)
    const ofBusiness: string = FRENCH_ELISION_START.test(business) ? `d'${business}` : `de ${business}`
    return GREETING_TEMPLATES[code][config.assistant_gender ?? 'feminine']
      .replace('{name}', config.assistant_name)
      .replace('{business}', business)
      .replace('{of_business}', ofBusiness)
  }

  /**
   * Open the thread with the greeting, once; laid out in a page it is typed first, as a real first reply would be.
   * @returns A promise resolved once the greeting is in the thread.
   */
  async function greet(): Promise<void> {
    if (messages.value.length !== 0) return
    if (inline) {
      isBusy.value = true
      await new Promise<void>((resolve: () => void): void => {
        setTimeout(resolve, INLINE_GREETING_DELAY_MS)
      })
      isBusy.value = false
      if (messages.value.length !== 0) return
    }
    messages.value.push({ role: 'assistant', content: greetingText(lang.value) })
  }

  /** Laid out in a page, the panel is open on arrival: the opening counts at the visitor's first interaction. */
  function noteInlineOpening(): void {
    if (!inline || hasCapturedInlineOpening.value) return
    hasCapturedInlineOpening.value = true
    captureDemoEvent('assistant_opened')
  }

  /**
   * Switch the widget's preset language (the assistant still replies in the visitor's own language).
   * @param code - The language code to switch to.
   */
  function setLang(code: AssistantWidgetLang): void {
    lang.value = code
    const greeting: AssistantChatMessage | undefined = messages.value[0]
    if (messages.value.length === 1 && greeting?.role === 'assistant') greeting.content = greetingText(code)
  }

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
        `${publicEndpoint}/appointment-slots`,
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
    if (isBusy.value || leadSent.value) return
    noteInlineOpening()
    hasOfferedBooking.value = true
    isPhotoPanelOpen.value = false
    showLeadForm.value = false
    isSlotPanelOpen.value = true
    // Free slots change: the agenda's are read again, from the first page, at each opening.
    if (slotsState.value !== 'ready' || bookingMode.value === 'calendar') await loadSlots()
  }

  /** Close the appointment panel and forget the picks. */
  function closeSlotPanel(): void {
    isSlotPanelOpen.value = false
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
    isSlotPanelOpen.value = false
    showLeadForm.value = true
  }

  /** Show the photo panel: its privacy note comes before the file picker. */
  function openPhotoPanel(): void {
    if (photosRemaining.value <= 0 || isBusy.value) return
    noteInlineOpening()
    isSlotPanelOpen.value = false
    showLeadForm.value = false
    isPhotoPanelOpen.value = true
  }

  /** Hide the photo panel. */
  function closePhotoPanel(): void {
    isPhotoPanelOpen.value = false
  }

  /** Show the contact form for a call back: an appointment picked before is not part of it. */
  function openLeadForm(): void {
    noteInlineOpening()
    forgetPicks()
    isPhotoPanelOpen.value = false
    isSlotPanelOpen.value = false
    showLeadForm.value = true
  }

  /** Close the contact form; an appointment's picks go with it. */
  function cancelLeadForm(): void {
    showLeadForm.value = false
    forgetPicks()
  }

  /**
   * Send a text as the visitor's message (an internal visit is flagged so it stays out of the counts).
   * @param text - The message to send.
   * @returns A promise resolving once the reply is handled.
   */
  async function sendText(text: string): Promise<void> {
    const trimmed: string = text.trim()
    if (!trimmed || isBusy.value) return
    noteInlineOpening()
    messages.value.push({ role: 'user', content: trimmed })
    captureDemoEvent('assistant_message_sent')
    draft.value = ''
    isBusy.value = true
    let offerBooking: boolean = false
    try {
      const answer: AssistantChatReply = await $fetch<AssistantChatReply>(`${publicEndpoint}/chat`, {
        method: 'POST',
        body: {
          messages: messages.value.slice(-MAX_STORED_MESSAGES),
          session_id: sessionId.value,
          language: lang.value,
          internal: DemoBeaconUtils.isInternalVisit(),
        },
      })
      messages.value.push({ role: 'assistant', content: answer.reply })
      offerBooking = answer.offer_booking
    } catch {
      messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[lang.value] })
    } finally {
      isBusy.value = false
    }
    if (offerBooking && !hasOfferedBooking.value && !showLeadForm.value) await openSlotPanel()
  }

  /**
   * Send the current draft as the visitor's message.
   * @returns A promise resolving once the reply is handled.
   */
  async function sendDraft(): Promise<void> {
    await sendText(draft.value)
  }

  /**
   * The visitor-facing message for a photo the API refused (quota, size, format) or could not take.
   * @param error - What the upload threw.
   * @returns A message in the widget language.
   */
  function photoErrorMessage(error: unknown): string {
    const status: number | undefined = ApiRefusalUtils.status(error)
    if (status === 409) {
      photosRemaining.value = 0
      return PHOTO_LABELS[lang.value].quota
    }
    if (status === 413) return PHOTO_LABELS[lang.value].tooLarge
    if (status === 415) return PHOTO_LABELS[lang.value].invalid
    return FALLBACK_REPLY[lang.value]
  }

  /**
   * Send a photo for a quote: thumbnail at once, the assistant's description, then the contact form prefilled.
   * @param file - The picked file.
   * @returns A promise resolved once the assistant has answered.
   */
  async function sendPhoto(file: File): Promise<void> {
    isPhotoPanelOpen.value = false
    if (isBusy.value) return
    if (!PhotoCompressionUtils.isPhoto(file)) {
      messages.value.push({ role: 'assistant', content: PHOTO_LABELS[lang.value].invalid })
      return
    }
    // Busy from the start: a second photo picked while this one compresses would slip past the quota.
    isBusy.value = true
    const upload: Blob = await PhotoCompressionUtils.prepare(file)
    if (upload.size > PhotoCompressionUtils.MAX_BYTES) {
      isBusy.value = false
      messages.value.push({ role: 'assistant', content: PHOTO_LABELS[lang.value].tooLarge })
      return
    }
    messages.value.push({ role: 'user', content: PHOTO_LABELS[lang.value].sent })
    const previewIndex: number = messages.value.length - 1
    const previewUrl: string = URL.createObjectURL(upload)
    photoPreviews.value = { ...photoPreviews.value, [previewIndex]: previewUrl }
    captureDemoEvent('assistant_photo_sent')
    try {
      const form: FormData = new FormData()
      form.append('file', upload, 'photo.jpg')
      form.append('session_id', sessionId.value)
      form.append('language', lang.value)
      form.append('internal', String(DemoBeaconUtils.isInternalVisit()))
      const answer: AssistantPhotoReply = await $fetch<AssistantPhotoReply>(`${publicEndpoint}/photo`, {
        method: 'POST',
        body: form,
      })
      messages.value.push({ role: 'assistant', content: answer.reply })
      photosRemaining.value = answer.remaining
      if (answer.accepted && !leadSent.value) {
        hasSentPhoto.value = true
        if (answer.need) leadNeedPrefill.value = answer.need
        showLeadForm.value = true
      }
    } catch (error: unknown) {
      // A refused photo is not shown as sent: its thumbnail goes, the refusal explains why.
      URL.revokeObjectURL(previewUrl)
      photoPreviews.value = Object.fromEntries(
        Object.entries(photoPreviews.value).filter(
          ([index]: [string, string]): boolean => Number(index) !== previewIndex,
        ),
      )
      messages.value[previewIndex] = { role: 'user', content: PHOTO_LABELS[lang.value].refused }
      messages.value.push({ role: 'assistant', content: photoErrorMessage(error) })
    } finally {
      isBusy.value = false
    }
  }

  /**
   * What the visitor reads once their details are sent.
   * @param reply - The API's answer.
   * @param booking - The free slot they picked, if any.
   * @returns The booked slot, the half-days (or the slot) the business will confirm, or the call-back promise.
   */
  function leadConfirmation(reply: AssistantLeadReply, booking: AssistantAppointmentTime | null): string {
    const labels: AssistantAppointmentLabels = APPOINTMENT_LABELS[lang.value]
    if (reply.booked_start) {
      const when: string = AssistantScheduleUtils.timeLabel(reply.booked_start, lang.value)
      const booked: string = labels.booked.replace('{slots}', chosenKind.value ? `${when} (${chosenKind.value})` : when)
      if (reply.confirmation_channel === 'sms') return booked + labels.bookedSms
      if (reply.confirmation_channel === 'email') return booked + labels.bookedEmail
      return booked
    }
    if (booking) return labels.sent.replace('{slots}', AssistantScheduleUtils.timeLabel(booking.start, lang.value))
    if (chosenSlots.value.length > 0) return labels.sent.replace('{slots}', chosenSlotsLine.value)
    return LEAD_LABELS[lang.value].sent
  }

  /**
   * What the request just sent holds, for the page showing what the business receives.
   * @param details - The details the visitor typed.
   * @param reply - The API's answer.
   * @param booking - The free slot picked, if any.
   * @returns The summary the page can turn into the business's alert.
   */
  function leadSummary(
    details: AssistantContactDetails,
    reply: AssistantLeadReply,
    booking: AssistantAppointmentTime | null,
  ): AssistantLeadSummary {
    const hasAppointment: boolean = booking !== null || chosenSlots.value.length > 0 || reply.booked_start !== null
    let slots: string = ''
    if (reply.booked_start) slots = AssistantScheduleUtils.timeLabel(reply.booked_start, lang.value)
    else if (booking) slots = AssistantScheduleUtils.timeLabel(booking.start, lang.value)
    else if (chosenSlots.value.length > 0) slots = chosenSlotsLine.value
    return {
      name: details.name.trim(),
      contact: details.contact.trim(),
      need: details.need.trim(),
      kind: hasAppointment ? 'appointment' : hasSentPhoto.value ? 'quote' : 'question',
      slots,
      booked: reply.booked_start !== null,
      hasPhoto: hasSentPhoto.value,
    }
  }

  /**
   * Send the visitor's details: the API turns them into a request tied to this conversation.
   * @param details - The name, contact and need typed.
   * @returns A promise resolved once the request is sent.
   */
  async function submitLead(details: AssistantContactDetails): Promise<void> {
    if (isSubmittingLead.value || !details.name.trim() || !details.contact.trim()) return
    isSubmittingLead.value = true
    const booking: AssistantAppointmentTime | null = bookingMode.value === 'calendar' ? chosenTime.value : null
    try {
      const reply: AssistantLeadReply = await $fetch<AssistantLeadReply>(`${publicEndpoint}/lead`, {
        method: 'POST',
        body: {
          name: details.name,
          contact: details.contact,
          need: details.need,
          language: lang.value,
          session_id: sessionId.value,
          internal: DemoBeaconUtils.isInternalVisit(),
          slots: booking ? [] : chosenSlots.value,
          booking: booking ? { start: booking.start, type: chosenKind.value } : null,
        },
      })
      leadSent.value = true
      captureDemoEvent('assistant_lead_submitted')
      showLeadForm.value = false
      messages.value.push({ role: 'assistant', content: leadConfirmation(reply, booking) })
      lastLeadSummary.value = leadSummary(details, reply, booking)
    } catch (error: unknown) {
      // A slot taken or withdrawn meanwhile answers 409: the offer is read again. A 422 carries a sentence
      // written for the visitor (a kind to choose, a test visit); anything else is a technical failure.
      const status: number | undefined = ApiRefusalUtils.status(error)
      const detail: string | null = ApiRefusalUtils.detail(error)
      const hasPick: boolean = booking !== null || chosenSlots.value.length > 0
      if (hasPick && status === 409) {
        const isWithdrawn: boolean = detail !== null && detail.includes('proposé')
        const notice: string = isWithdrawn
          ? APPOINTMENT_LABELS[lang.value].unavailable
          : APPOINTMENT_LABELS[lang.value].taken
        messages.value.push({ role: 'assistant', content: notice })
        forgetPicks()
        showLeadForm.value = false
        isSlotPanelOpen.value = true
        await loadSlots()
      } else if (status === 422 && detail !== null) {
        messages.value.push({ role: 'assistant', content: detail })
      } else {
        messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[lang.value] })
      }
    } finally {
      isSubmittingLead.value = false
    }
  }

  /** Free the thumbnails' object URLs when the widget leaves the page. */
  function releasePhotoPreviews(): void {
    Object.values(photoPreviews.value).forEach((url: string): void => URL.revokeObjectURL(url))
  }

  watch([messages, lang], (): void => persistConversation(), { deep: true })

  return {
    messages,
    lang,
    offeredLanguages,
    suggestions,
    draft,
    isBusy,
    photoPreviews,
    photosRemaining,
    isPhotoPanelOpen,
    isSlotPanelOpen,
    showLeadForm,
    leadSent,
    isSubmittingLead,
    leadNeedPrefill,
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
    canContinueBooking,
    pickedSummary,
    showChips,
    showCallbackBar,
    lastLeadSummary,
    restore,
    greet,
    setLang,
    sendText,
    sendDraft,
    openPhotoPanel,
    closePhotoPanel,
    sendPhoto,
    openSlotPanel,
    closeSlotPanel,
    loadFirstSlotsPage,
    showMoreTimes,
    toggleSlot,
    chooseTime,
    chooseKind,
    confirmSlots,
    openLeadForm,
    cancelLeadForm,
    submitLead,
    releasePhotoPreviews,
  }
}
