import type { ComputedRef, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type {
  AiAssistantConfig,
  AssistantChatMessage,
  AssistantChatReply,
  AssistantChatRequestBody,
  AssistantWidgetLanguage,
} from '~/types/AiAssistant'
import type { AssistantDemoScriptStep, AssistantHostPage } from '~/types/AssistantDemoScript'
import type { AssistantStoredConversation, AssistantThreadContext, AssistantThreadPanel } from '~/types/AssistantThread'
import type { UseAssistantBookingReturn } from '~/types/UseAssistantBooking'
import type { UseAssistantConversationReturn } from '~/types/UseAssistantConversation'
import type { UseAssistantLeadFormReturn } from '~/types/UseAssistantLeadForm'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'
import { useAssistantBooking } from '~/composables/useAssistantBooking'
import { useAssistantLeadForm } from '~/composables/useAssistantLeadForm'
import { useAssistantPhotoUpload } from '~/composables/useAssistantPhotoUpload'
import { postHostPersist } from '~/composables/useAssistantWidgetFrame'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { FALLBACK_REPLY, GREETING_FOLLOW_UPS, GREETING_INTROS, SUGGESTIONS } from '~/constants/AssistantWidgetLabels'
import { ASSISTANT_STORED_MESSAGES_MAX } from '~/constants/AssistantWidgetLimits'
import { AssistantConversationStorageUtils } from '~/utils/AssistantConversationStorageUtils'
import { AssistantHostPageUtils } from '~/utils/AssistantHostPageUtils'
import { AssistantLanguageUtils } from '~/utils/AssistantLanguageUtils'
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

/** A French word starting with a vowel or a mute h takes « d' » (« d'Atelier ») rather than « de ». */
const FRENCH_ELISION_START: RegExp = /^[aeiouyàâäéèêëîïôöùûüh]/i

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

  const messages: Ref<AssistantChatMessage[]> = ref([])
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
  let isPlayingExample: boolean = false
  let hasCapturedInlineOpening: boolean = false

  const context: AssistantThreadContext = {
    assistant,
    publicEndpoint,
    messages,
    language,
    sessionId,
    isBusy,
    openPanel,
    hasSentLead,
    noteInlineOpening,
  }
  const booking: UseAssistantBookingReturn = useAssistantBooking(context)
  const photo: UseAssistantPhotoUploadReturn = useAssistantPhotoUpload(context)
  const leadForm: UseAssistantLeadFormReturn = useAssistantLeadForm(context, booking, photo)

  const offeredLanguages: ComputedRef<AssistantWidgetLanguage[]> = computed((): AssistantWidgetLanguage[] =>
    AssistantLanguageUtils.offered(assistant.languages),
  )
  const suggestions: ComputedRef<string[]> = computed((): string[] => SUGGESTIONS[language.value])
  /** The opening chips show under the greeting only, until the visitor writes or opens a panel. */
  const shouldShowOpeningChips: ComputedRef<boolean> = computed(
    (): boolean => messages.value.length <= 1 && openPanel.value === null,
  )
  /** The thread ends on a reply the visitor may act on: nothing typing, no panel open. */
  const endsOnReply: ComputedRef<boolean> = computed((): boolean => {
    const last: AssistantChatMessage | undefined = messages.value[messages.value.length - 1]
    return (
      messages.value.length > 1 &&
      last?.role === 'assistant' &&
      !isBusy.value &&
      !isStreaming.value &&
      openPanel.value === null
    )
  })
  /** The questions the last reply offers next, as chips under it, until the visitor goes on. */
  const followUps: ComputedRef<string[]> = computed((): string[] => {
    const last: AssistantChatMessage | undefined = messages.value[messages.value.length - 1]
    return endsOnReply.value && last?.follow_ups?.length ? last.follow_ups : []
  })
  /** A reply without questions still offers the two actions (photo, appointment), so the visitor can click on. */
  const shouldShowActionChips: ComputedRef<boolean> = computed(
    (): boolean =>
      endsOnReply.value && followUps.value.length === 0 && (photo.photosRemaining.value > 0 || !hasSentLead.value),
  )
  /** A slim way to leave one's details stays above the composer, from the greeting until the request is sent. */
  const shouldShowCallbackBar: ComputedRef<boolean> = computed(
    (): boolean => !hasSentLead.value && openPanel.value === null,
  )

  /**
   * Take a stored conversation: its session, its language when still offered, and its thread when it has one.
   * @param stored - The conversation read back, or null.
   * @returns True when a thread was restored (so the widget skips the fresh greeting).
   */
  function applyStoredConversation(stored: AssistantStoredConversation | null): boolean {
    if (!stored) return false
    if (stored.sessionId) sessionId.value = stored.sessionId
    const storedLanguage: AssistantWidgetLanguage | undefined = offeredLanguages.value.find(
      (code: AssistantWidgetLanguage): boolean => code === stored.language,
    )
    if (storedLanguage) language.value = storedLanguage
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
    const hasSpoken: boolean = messages.value.some((message: AssistantChatMessage): boolean => message.role === 'user')
    if (hasSpoken || !raw) return
    applyStoredConversation(AssistantConversationStorageUtils.parse(raw))
  }

  /** Persist this visitor's conversation and language, bounded to the most recent messages. */
  function persistConversation(): void {
    // An empty thread has nothing to save, and saving it would wipe the copy the host page keeps from an earlier page.
    if (messages.value.length === 0) return
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
    const ofBusiness: string = FRENCH_ELISION_START.test(business) ? `d'${business}` : `de ${business}`
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
   * typing; the demo page then hands over to the visitor. Only laid out in a page, once.
   * @param steps - The turns to play.
   * @returns A promise resolved once the last turn is in the thread.
   */
  async function playExample(steps: AssistantDemoScriptStep[]): Promise<void> {
    if (!inline || isBusy.value || isPlayingExample || hasPlayedExample.value) return
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
      messages.value.push({ role: step.role, content: step.content })
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
    const greeting: AssistantChatMessage | undefined = messages.value[0]
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
   * Send a text as the visitor's message (an internal visit is flagged so it stays out of the counts).
   * @param text - The message to send.
   * @returns A promise resolving once the reply is handled.
   */
  async function sendText(text: string): Promise<void> {
    const trimmed: string = text.trim()
    if (!trimmed || isBusy.value || isStreaming.value) return
    noteInlineOpening()
    messages.value.push({ role: 'user', content: trimmed })
    // A visitor writing in another offered language moves the widget to it; a short line leaves it as is.
    const hasFollowedVisitor: boolean = followLanguage(trimmed)
    captureDemoEvent('assistant_message_sent')
    draft.value = ''
    isBusy.value = true
    let offerBooking: boolean = false
    const body: AssistantChatRequestBody = {
      messages: AssistantThreadUtils.conversationTurns(messages.value),
      session_id: sessionId.value,
      language: language.value,
      internal: DemoBeaconUtils.isInternalVisit(),
    }
    try {
      let answer: AssistantChatReply | null = await streamReply(body)
      if (!answer) {
        answer = await $fetch<AssistantChatReply>(`${publicEndpoint}/chat`, { method: 'POST', body })
        messages.value.push(AssistantThreadUtils.replyMessage(answer.reply, answer.follow_ups))
      }
      offerBooking = answer.offer_booking
      // The reply is longer than the question: when the question was too short to tell, the reply decides.
      if (!hasFollowedVisitor) followLanguage(answer.reply)
    } catch {
      messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[language.value] })
    } finally {
      isBusy.value = false
      isStreaming.value = false
    }
    if (offerBooking && !booking.hasOfferedBooking.value && !leadForm.isLeadFormOpen.value) {
      await booking.openSlotPanel()
    }
  }

  /**
   * Ask for the reply as a stream, growing the assistant's bubble as the text lands.
   * @param body - The chat request.
   * @returns The whole reply, or null when the stream is unavailable or broke (the plain request takes over).
   */
  async function streamReply(body: AssistantChatRequestBody): Promise<AssistantChatReply | null> {
    let response: Response
    try {
      response = await fetch(`${publicEndpoint}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    } catch {
      return null
    }
    if (!response.ok) return null
    let bubbleIndex: number = -1
    const closing: AssistantChatReply | null = await AssistantStreamUtils.read(response, (delta: string): void => {
      if (bubbleIndex === -1) {
        isBusy.value = false
        isStreaming.value = true
        bubbleIndex = messages.value.push({ role: 'assistant', content: '' }) - 1
      }
      const bubble: AssistantChatMessage | undefined = messages.value[bubbleIndex]
      if (bubble) bubble.content += delta
    })
    if (!closing) {
      // A stream cut mid-way would leave a truncated reply: the plain request answers instead.
      if (bubbleIndex !== -1) messages.value.splice(bubbleIndex, 1)
      isStreaming.value = false
      isBusy.value = true
      return null
    }
    const bubble: AssistantChatMessage | undefined = messages.value[bubbleIndex]
    if (bubble && closing.reply) bubble.content = closing.reply
    else if (!bubble && closing.reply) {
      messages.value.push(AssistantThreadUtils.replyMessage(closing.reply, closing.follow_ups))
    }
    if (bubble && closing.follow_ups.length > 0) bubble.follow_ups = closing.follow_ups
    return closing
  }

  /**
   * Send the current draft as the visitor's message.
   * @returns A promise resolving once the reply is handled.
   */
  async function sendDraft(): Promise<void> {
    await sendText(draft.value)
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
    sendText,
    sendDraft,
    ...booking,
    ...photo,
    ...leadForm,
  }
}
