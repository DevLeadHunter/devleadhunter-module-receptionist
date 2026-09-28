import type { ComputedRef, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type {
  AiAssistantConfig,
  AssistantChatReply,
  AssistantChatRequestBody,
  AssistantErrorLabels,
  AssistantThreadMessage,
  AssistantWidgetLanguage,
} from '~/types/AiAssistant'
import type { AssistantDemoScriptStep, AssistantHostPage } from '~/types/AssistantDemoScript'
import type { AssistantReplyOutcome, AssistantRequestFailure, AssistantStreamOutcome } from '~/types/AssistantRequest'
import type {
  AssistantStoredConversation,
  AssistantConversationThread,
  AssistantThreadPanel,
} from '~/types/AssistantThread'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import type { UseAssistantConversationReturn } from '~/types/UseAssistantConversation'
import type { UseAssistantLeadFormReturn } from '~/types/UseAssistantLeadForm'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'
import { useAssistantBooking } from '~/composables/useAssistantBooking'
import { useAssistantLeadForm } from '~/composables/useAssistantLeadForm'
import { useAssistantPhotoUpload } from '~/composables/useAssistantPhotoUpload'
import { postHostPersist } from '~/composables/useAssistantWidgetFrame'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { ERROR_LABELS, GREETING_FOLLOW_UPS, GREETING_INTROS, SUGGESTIONS } from '~/constants/AssistantWidgetLabels'
import { ASSISTANT_STORED_MESSAGES_MAX } from '~/constants/AssistantWidgetLimits'
import { AssistantConversationStorageUtils } from '~/utils/AssistantConversationStorageUtils'
import { AssistantHostPageUtils } from '~/utils/AssistantHostPageUtils'
import { AssistantLanguageUtils } from '~/utils/AssistantLanguageUtils'
import { AssistantRequestUtils } from '~/utils/AssistantRequestUtils'
import { AssistantStreamUtils } from '~/utils/AssistantStreamUtils'
import { AssistantThreadUtils } from '~/utils/AssistantThreadUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { LanguageDetectUtils } from '~/utils/LanguageDetectUtils'

/** Laid out in a page, the greeting is typed before it appears, like a first reply; the panel is on screen already. */
const INLINE_GREETING_DELAY_MS: number = 900

/** In the played example, a visitor line lands after this pause and a reply is typed for that long. */
const EXAMPLE_VISITOR_DELAY_MS: number = 900
const EXAMPLE_REPLY_DELAY_MS: number = 1500

/** A sold receptionist answers a business's own customers: the demo page's played example is a sales pitch. */
const DELIVERED_STATUS: string = 'delivered'

/**
 * A pause, for the typed greeting and the played example.
 * @param milliseconds - How long.
 * @returns A promise resolved after the pause.
 */
function wait(milliseconds: number): Promise<void> {
  return new Promise<void>((resolve: () => void): void => {
    setTimeout(resolve, milliseconds)
  })
}

/**
 * The visitor's conversation with an assistant: the thread, its language, the photo, the slots and the contact form.
 * @param assistant - The assistant's public configuration.
 * @param inline - Whether the panel is laid out in a page (the demo phone) rather than floating.
 * @param hostPage - The client's page the loader embedded the widget on, or null.
 * @returns The state and the actions the widget binds.
 */
export function useAssistantConversation(
  assistant: AiAssistantConfig,
  inline: boolean,
  hostPage: AssistantHostPage | null,
): UseAssistantConversationReturn {
  const runtimeConfig: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
  const publicEndpoint: string = `${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${assistant.slug}`
  const storageKey: string = AssistantConversationStorageUtils.key(assistant.slug)

  const messages: Ref<AssistantThreadMessage[]> = ref([])
  const language: Ref<AssistantWidgetLanguage> = ref(AssistantLanguageUtils.DEFAULT_LANGUAGE)
  const draft: Ref<string> = ref('')
  const isBusy: Ref<boolean> = ref(false)
  /** True while a reply is still arriving piece by piece in its bubble. */
  const isStreaming: Ref<boolean> = ref(false)
  const hasPlayedExample: Ref<boolean> = ref(false)
  /** Random id sent with every turn so the server journal groups this visitor's conversation. */
  const sessionId: Ref<string> = ref('')
  const openPanel: Ref<AssistantThreadPanel | null> = ref(null)
  const hasSentLead: Ref<boolean> = ref(false)
  const isAssistantUnavailable: Ref<boolean> = ref(false)
  let isPlayingExample: boolean = false
  let hasCapturedInlineOpening: boolean = false

  const thread: AssistantConversationThread = {
    publicEndpoint,
    messages,
    language,
    sessionId,
    isBusy,
    openPanel,
    hasSentLead,
    isAssistantUnavailable,
    noteInlineOpening,
    pushLocalLine,
    reportFailure,
  }
  const booking: UseAssistantBookingReturn = useAssistantBooking(thread)
  const photo: UseAssistantPhotoUploadReturn = useAssistantPhotoUpload(thread)
  const leadForm: UseAssistantLeadFormReturn = useAssistantLeadForm(thread, booking, photo)

  const offeredLanguages: ComputedRef<AssistantWidgetLanguage[]> = computed((): AssistantWidgetLanguage[] =>
    AssistantLanguageUtils.offered(assistant.languages),
  )
  const suggestions: ComputedRef<string[]> = computed((): string[] => SUGGESTIONS[language.value])
  const canPlayExample: ComputedRef<boolean> = computed(
    (): boolean => inline && !hasPlayedExample.value && assistant.status !== DELIVERED_STATUS,
  )
  /** The opening chips show under the greeting only, until the visitor writes or opens a panel. */
  const shouldShowOpeningChips: ComputedRef<boolean> = computed(
    (): boolean => messages.value.length <= 1 && openPanel.value === null && !isAssistantUnavailable.value,
  )
  /** The thread ends on a reply the visitor may act on: nothing typing, no panel open. */
  const endsOnReply: ComputedRef<boolean> = computed((): boolean => {
    const last: AssistantThreadMessage | undefined = messages.value[messages.value.length - 1]
    return (
      messages.value.length > 1 &&
      last?.role === 'assistant' &&
      !isBusy.value &&
      !isStreaming.value &&
      openPanel.value === null &&
      !isAssistantUnavailable.value
    )
  })
  /** The questions the last reply offers next, as chips under it, until the visitor goes on. */
  const followUps: ComputedRef<string[]> = computed((): string[] => {
    const last: AssistantThreadMessage | undefined = messages.value[messages.value.length - 1]
    return endsOnReply.value && last?.follow_ups?.length ? last.follow_ups : []
  })
  /** A reply without questions still offers the two actions (photo, appointment), so the visitor can click on. */
  const shouldShowActionChips: ComputedRef<boolean> = computed(
    (): boolean =>
      endsOnReply.value && followUps.value.length === 0 && (photo.photosRemaining.value > 0 || !hasSentLead.value),
  )
  /** A slim way to leave one's details stays above the composer, from the greeting until the request is sent. */
  const shouldShowCallbackBar: ComputedRef<boolean> = computed(
    (): boolean => !hasSentLead.value && openPanel.value === null && !isAssistantUnavailable.value,
  )

  /**
   * Add one of the widget's own lines to the thread (shown, never stored nor sent to the model).
   * @param content - The line.
   * @param role - Whose side it shows on.
   */
  function pushLocalLine(content: string, role: AssistantThreadMessage['role'] = 'assistant'): void {
    messages.value.push(AssistantThreadUtils.localLine(content, role))
  }

  /**
   * Tell the visitor a call failed; a gone assistant closes what is open and stops offering the input.
   * @param failure - Why the call failed.
   */
  function reportFailure(failure: AssistantRequestFailure): void {
    if (isAssistantUnavailable.value) return
    captureDemoEvent('assistant_request_failed', { reason: failure })
    const labels: AssistantErrorLabels = ERROR_LABELS[language.value]
    if (failure === 'unavailable') {
      isAssistantUnavailable.value = true
      openPanel.value = null
      pushLocalLine(
        labels.unavailable
          .replace('{name}', assistant.assistant_name)
          .replace('{business}', BusinessNameUtils.short(assistant.business_name)),
      )
      return
    }
    if (failure === 'rate-limited') pushLocalLine(labels.rateLimited)
    else if (failure === 'network') pushLocalLine(labels.network)
    else pushLocalLine(labels.server)
  }

  /**
   * Take a stored conversation: its session, its language when still offered, and its thread when it has one.
   * @param stored - The conversation read back, or null.
   * @returns True when a thread was restored (so the widget skips the fresh greeting).
   */
  function applyStoredConversation(stored: AssistantStoredConversation | null): boolean {
    if (!stored) return false
    if (stored.sessionId) sessionId.value = stored.sessionId
    const storedLanguage: AssistantWidgetLanguage | null = AssistantLanguageUtils.fromStoredCode(stored.language)
    if (storedLanguage && offeredLanguages.value.includes(storedLanguage)) language.value = storedLanguage
    if (!stored.messages.length) return false
    messages.value = stored.messages.slice(-ASSISTANT_STORED_MESSAGES_MAX)
    return true
  }

  /**
   * Take the conversation the host page kept, when this widget has nothing yet but its greeting: Safari gives a
   * third-party iframe no storage of its own, the host page's copy carries the thread from page to page.
   * @param raw - The serialised conversation the loader sent, or null when the host page has none.
   */
  function restoreFromHost(raw: string | null): void {
    const hasSpoken: boolean = AssistantThreadUtils.conversationOf(messages.value).some(
      (message: AssistantThreadMessage): boolean => message.role === 'user',
    )
    if (hasSpoken || !raw) return
    applyStoredConversation(AssistantConversationStorageUtils.parse(raw))
  }

  /** Persist this visitor's conversation and language, bounded to the most recent messages. */
  function persistConversation(): void {
    // An empty thread has nothing to save, and saving it would wipe the copy the host page keeps from an earlier page.
    if (AssistantThreadUtils.conversationOf(messages.value).length === 0) return
    const raw: string = AssistantConversationStorageUtils.serialize(language.value, sessionId.value, messages.value)
    AssistantConversationStorageUtils.write(storageKey, raw)
    if (!inline) postHostPersist(raw)
  }

  /**
   * The visitor's browser language, when the assistant offers it.
   * @returns The matching offered language, or null when none of the visitor's languages is offered.
   */
  function browserLanguage(): AssistantWidgetLanguage | null {
    if (typeof navigator === 'undefined') return null
    return AssistantLanguageUtils.firstOffered(
      [navigator.language, ...(navigator.languages ?? [])],
      offeredLanguages.value,
    )
  }

  /** Restore a returning visitor's conversation, else open in their browser language when offered. */
  function restore(): void {
    const stored: AssistantStoredConversation | null = AssistantConversationStorageUtils.parse(
      AssistantConversationStorageUtils.read(storageKey),
    )
    if (!applyStoredConversation(stored)) {
      const preferred: AssistantWidgetLanguage | null = browserLanguage()
      if (preferred) language.value = preferred
    }
    if (!sessionId.value) sessionId.value = AssistantConversationStorageUtils.newSessionId()
  }

  /**
   * The greeting in a language: the persona introduces itself as the business's AI receptionist, then asks.
   * @param greetingLanguage - The language of the greeting.
   * @returns The greeting text.
   */
  function greetingText(greetingLanguage: AssistantWidgetLanguage): string {
    const business: string = BusinessNameUtils.short(assistant.business_name)
    const ofBusiness: string = BusinessNameUtils.ofBusiness(business)
    const intro: string = GREETING_INTROS[greetingLanguage][assistant.assistant_gender ?? 'feminine']
      .replace('{name}', assistant.assistant_name)
      .replace('{business}', business)
      .replace('{of_business}', ofBusiness)
    return `${intro} ${GREETING_FOLLOW_UPS[greetingLanguage][AssistantHostPageUtils.context(hostPage)]}`
  }

  /**
   * Open the thread with the greeting, once; laid out in a page it is typed first, as a real first reply would be.
   * @returns A promise resolved once the greeting is in the thread.
   */
  async function greet(): Promise<void> {
    if (messages.value.length !== 0) return
    if (inline) {
      isBusy.value = true
      await wait(INLINE_GREETING_DELAY_MS)
      isBusy.value = false
      if (messages.value.length !== 0) return
    }
    messages.value.push({ role: 'assistant', content: greetingText(language.value) })
  }

  /**
   * Play a scripted conversation in the thread, turn by turn, as if a customer were writing and the assistant
   * typing; the demo page then hands over to the visitor. Only laid out in a page, once, never for a sold assistant.
   * @param steps - The turns to play.
   * @returns A promise resolved once the last turn is in the thread.
   */
  async function playExample(steps: AssistantDemoScriptStep[]): Promise<void> {
    if (!canPlayExample.value || isBusy.value || isPlayingExample) return
    isPlayingExample = true
    noteInlineOpening()
    captureDemoEvent('assistant_example_played')
    for (const step of steps) {
      if (step.role === 'assistant') {
        isBusy.value = true
        await wait(EXAMPLE_REPLY_DELAY_MS)
        isBusy.value = false
      } else {
        await wait(EXAMPLE_VISITOR_DELAY_MS)
      }
      // The scripted customer's photo shows in its bubble, like a real upload would.
      if (step.photoUrl) photo.showPhotoPreview(messages.value.length, step.photoUrl)
      pushLocalLine(step.content, step.role)
    }
    isPlayingExample = false
    hasPlayedExample.value = true
  }

  /** Laid out in a page, the panel is open on arrival: the opening counts at the visitor's first interaction. */
  function noteInlineOpening(): void {
    if (!inline || hasCapturedInlineOpening) return
    hasCapturedInlineOpening = true
    captureDemoEvent('assistant_opened')
  }

  /**
   * Switch the widget's preset language (the assistant still replies in the visitor's own language).
   * @param nextLanguage - The language to switch to.
   */
  function setLanguage(nextLanguage: AssistantWidgetLanguage): void {
    language.value = nextLanguage
    const greeting: AssistantThreadMessage | undefined = messages.value[0]
    if (messages.value.length === 1 && greeting?.role === 'assistant') greeting.content = greetingText(nextLanguage)
  }

  /**
   * Switch the widget's own language (labels, chips, language menu) to the one a text is clearly written in,
   * when the assistant offers it; the assistant already replies in the visitor's language.
   * @param text - The visitor's message, or the assistant's reply.
   * @returns True when the language changed.
   */
  function followLanguage(text: string): boolean {
    const detected: AssistantWidgetLanguage | null = LanguageDetectUtils.detect(text, offeredLanguages.value)
    if (detected === null || detected === language.value) return false
    language.value = detected
    return true
  }

  /**
   * Ask for the reply as a stream, growing the assistant's bubble as the text lands.
   * @param body - The chat request.
   * @returns The whole reply, a failure, or `fallback` when the stream is unusable (its partial bubble removed).
   */
  async function streamReply(body: AssistantChatRequestBody): Promise<AssistantStreamOutcome> {
    let bubbleIndex: number = -1
    const outcome: AssistantStreamOutcome = await AssistantStreamUtils.request(
      `${publicEndpoint}/chat/stream`,
      body,
      (delta: string): void => {
        if (bubbleIndex === -1) {
          isBusy.value = false
          isStreaming.value = true
          bubbleIndex = messages.value.push({ role: 'assistant', content: '' }) - 1
        }
        const bubble: AssistantThreadMessage | undefined = messages.value[bubbleIndex]
        if (bubble) bubble.content += delta
      },
    )
    if (outcome.kind === 'fallback') {
      // A stream cut mid-way would leave a truncated reply: the plain request answers instead.
      if (bubbleIndex !== -1) messages.value.splice(bubbleIndex, 1)
      isStreaming.value = false
      isBusy.value = true
      return outcome
    }
    if (outcome.kind === 'failure') return outcome
    const closing: AssistantChatReply = outcome.reply
    const bubble: AssistantThreadMessage | undefined = messages.value[bubbleIndex]
    if (bubble && closing.reply) bubble.content = closing.reply
    else if (!bubble && closing.reply) {
      messages.value.push(AssistantThreadUtils.replyMessage(closing.reply, closing.follow_ups))
    }
    if (bubble && closing.follow_ups.length > 0) bubble.follow_ups = closing.follow_ups
    return outcome
  }

  /**
   * The assistant's reply: streamed, else asked in one piece; bounded in time either way.
   * @param body - The chat request.
   * @returns The reply, or why it did not come.
   */
  async function requestReply(body: AssistantChatRequestBody): Promise<AssistantReplyOutcome> {
    const streamed: AssistantStreamOutcome = await streamReply(body)
    if (streamed.kind !== 'fallback') return streamed
    try {
      const reply: AssistantChatReply = await AssistantRequestUtils.fetchChatReply(publicEndpoint, body)
      messages.value.push(AssistantThreadUtils.replyMessage(reply.reply, reply.follow_ups))
      return { kind: 'reply', reply }
    } catch (error: unknown) {
      return { kind: 'failure', failure: AssistantRequestUtils.failureOf(error) }
    }
  }

  /**
   * Act on what a reply carries beyond its text: the contact it filed, the daily limit, an appointment asked for.
   * @param reply - The reply.
   * @returns A promise resolved once the slot panel is loaded, when it opens.
   */
  async function actOnReply(reply: AssistantChatReply): Promise<void> {
    if (reply.captured_contact) leadForm.confirmCapturedContact(reply.captured_contact)
    if (reply.daily_limit_reached) {
      captureDemoEvent('assistant_daily_limit_reached')
      if (!hasSentLead.value) leadForm.openLeadForm()
      return
    }
    if (reply.offer_booking && !booking.hasOfferedBooking.value && !leadForm.isLeadFormOpen.value) {
      await booking.openSlotPanel()
    }
  }

  /**
   * Send a text as the visitor's message (an internal visit is flagged so it stays out of the counts).
   * @param text - The message to send.
   * @returns A promise resolving to true once the reply is in the thread, false when nothing was sent.
   */
  async function sendVisitorMessage(text: string): Promise<boolean> {
    const trimmed: string = text.trim()
    if (!trimmed || isBusy.value || isStreaming.value || isAssistantUnavailable.value) return false
    noteInlineOpening()
    const visitorIndex: number = messages.value.push({ role: 'user', content: trimmed }) - 1
    // A visitor writing in another offered language moves the widget to it; a short line leaves it as is.
    const hasFollowedVisitor: boolean = followLanguage(trimmed)
    captureDemoEvent('assistant_message_sent')
    isBusy.value = true
    const body: AssistantChatRequestBody = {
      messages: AssistantThreadUtils.conversationTurns(messages.value),
      session_id: sessionId.value,
      language: language.value,
      internal: DemoBeaconUtils.isInternalVisit(),
      visitor_name: leadForm.leadPrefill.value.name || undefined,
    }
    let outcome: AssistantReplyOutcome
    try {
      outcome = await requestReply(body)
    } finally {
      isBusy.value = false
      isStreaming.value = false
    }
    if (outcome.kind === 'failure') {
      // Unanswered, the message leaves the thread (its partial reply too): sent again, it would show twice.
      messages.value.splice(visitorIndex)
      reportFailure(outcome.failure)
      return false
    }
    // The reply is longer than the question: when the question was too short to tell, the reply decides.
    if (!hasFollowedVisitor) followLanguage(outcome.reply.reply)
    await actOnReply(outcome.reply)
    return true
  }

  /**
   * Send the draft as the visitor's message; the field empties at once and gets the text back if it did not go.
   * @returns A promise resolving once the reply is handled.
   */
  async function sendDraft(): Promise<void> {
    const text: string = draft.value.trim()
    if (!text || isBusy.value || isStreaming.value || isAssistantUnavailable.value) return
    draft.value = ''
    const isAnswered: boolean = await sendVisitorMessage(text)
    // A draft typed meanwhile is the visitor's latest words: it stays.
    if (!isAnswered && !draft.value.trim()) draft.value = text
  }

  watch([messages, language], (): void => persistConversation(), { deep: true })

  return {
    messages,
    language,
    offeredLanguages,
    suggestions,
    draft,
    isBusy,
    isStreaming,
    hasSentLead,
    isAssistantUnavailable,
    canPlayExample,
    shouldShowOpeningChips,
    followUps,
    shouldShowActionChips,
    shouldShowCallbackBar,
    hasPlayedExample,
    restore,
    restoreFromHost,
    greet,
    playExample,
    setLanguage,
    sendSuggestion: sendVisitorMessage,
    sendDraft,
    bookingMode: booking.bookingMode,
    slotsState: booking.slotsState,
    slotDays: booking.slotDays,
    slotTimes: booking.slotTimes,
    hasMoreTimes: booking.hasMoreTimes,
    hasPreviousSlotsPage: booking.hasPreviousSlotsPage,
    appointmentKinds: booking.appointmentKinds,
    chosenSlots: booking.chosenSlots,
    chosenTime: booking.chosenTime,
    chosenKind: booking.chosenKind,
    canContinueBooking: booking.canContinueBooking,
    pickedSummary: booking.pickedSummary,
    isSlotPanelOpen: booking.isSlotPanelOpen,
    openSlotPanel: booking.openSlotPanel,
    closeSlotPanel: booking.closeSlotPanel,
    loadFirstSlotsPage: booking.loadFirstSlotsPage,
    showMoreTimes: booking.showMoreTimes,
    toggleSlot: booking.toggleSlot,
    chooseTime: booking.chooseTime,
    chooseKind: booking.chooseKind,
    confirmSlots: booking.confirmSlots,
    photoPreviews: photo.photoPreviews,
    photosRemaining: photo.photosRemaining,
    leadNeedPrefill: photo.leadNeedPrefill,
    isPhotoPanelOpen: photo.isPhotoPanelOpen,
    openPhotoPanel: photo.openPhotoPanel,
    closePhotoPanel: photo.closePhotoPanel,
    sendPhoto: photo.sendPhoto,
    releasePhotoPreviews: photo.releasePhotoPreviews,
    isLeadFormOpen: leadForm.isLeadFormOpen,
    isSubmittingLead: leadForm.isSubmittingLead,
    leadPrefill: leadForm.leadPrefill,
    lastLeadSummary: leadForm.lastLeadSummary,
    openLeadForm: leadForm.openLeadForm,
    cancelLeadForm: leadForm.cancelLeadForm,
    submitLead: leadForm.submitLead,
  }
}
