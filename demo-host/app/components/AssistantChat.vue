<template>
  <div class="ai-widget" :style="accentStyle">
    <button
      v-if="!isOpen"
      ref="launcherEl"
      type="button"
      class="ai-launcher"
      :class="{ 'ai-launcher--mobile': isMobileLayout }"
      :aria-label="`Ouvrir ${config.assistant_name}`"
      @click="open"
    >
      <span class="ai-launcher__say">
        Une question&nbsp;? <strong>{{ config.assistant_name }}</strong> vous répond, 24h/24.
      </span>
      <span class="ai-launcher__orb" aria-hidden="true"><AssistantAvatar /></span>
    </button>

    <section
      v-else
      class="ai-panel"
      :class="{ 'ai-panel--mobile': isMobileLayout }"
      role="dialog"
      :aria-label="config.assistant_name"
      @keydown.esc="close"
    >
      <header class="ai-head">
        <span class="ai-head__av"><AssistantAvatar /></span>
        <span class="ai-head__who">
          <b>{{ config.assistant_name }}</b>
          <span>{{ roleLabel }} {{ config.business_name }} · en ligne</span>
        </span>
        <button ref="closeEl" type="button" class="ai-head__x" aria-label="Fermer" @click="close">✕</button>
      </header>
      <p class="ai-sub">{{ languagesLine }}</p>

      <div v-if="offeredLanguages.length > 1" class="ai-langs">
        <button
          v-for="code in offeredLanguages"
          :key="code"
          type="button"
          :aria-pressed="code === lang"
          @click="setLang(code)"
        >
          {{ LANGUAGE_LABELS[code] }}
        </button>
      </div>

      <div ref="messagesEl" class="ai-msgs" role="log" aria-live="polite" aria-relevant="additions">
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="ai-m"
          :class="[`ai-m--${message.role}`, { 'ai-m--photo': photoPreviews[index] }]"
        >
          <img v-if="photoPreviews[index]" :src="photoPreviews[index]" :alt="message.content" class="ai-m__photo" />
          <template v-else-if="message.role === 'assistant'">
            <template v-for="(part, partIndex) in MessageLinkUtils.parts(message.content)" :key="partIndex">
              <a
                v-if="part.kind === 'link'"
                :href="part.value"
                target="_blank"
                rel="noopener noreferrer nofollow"
                class="ai-m__link"
                >{{ part.value }}</a
              >
              <template v-else>{{ part.value }}</template>
            </template>
          </template>
          <template v-else>{{ message.content }}</template>
        </div>
        <div v-if="isBusy" class="ai-typing" aria-label="Rédaction en cours"><i /><i /><i /></div>
      </div>

      <div v-if="messages.length <= 1 && !isSlotPanelOpen && !isPhotoPanelOpen && !showLeadForm" class="ai-chips">
        <button type="button" class="ai-chips__action" @click="openPhotoPanel">
          <svg
            class="ai-chips__icon"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
            <circle cx="12" cy="13" r="3" />
          </svg>
          {{ PHOTO_LABELS[lang].chip }}
        </button>
        <button type="button" class="ai-chips__action" @click="openSlotPanel">
          <svg
            class="ai-chips__icon"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <rect x="3.5" y="5" width="17" height="15" rx="2" />
            <path d="M3.5 10h17M8 3v4M16 3v4" />
          </svg>
          {{ APPOINTMENT_LABELS[lang].chip }}
        </button>
        <button v-for="suggestion in suggestions" :key="suggestion" type="button" @click="sendText(suggestion)">
          {{ suggestion }}
        </button>
      </div>

      <div v-if="isPhotoPanelOpen" class="ai-sheet ai-photo">
        <p class="ai-sheet__note">{{ PHOTO_LABELS[lang].note }}</p>
        <div class="ai-actions">
          <button type="button" class="ai-actions__primary" :disabled="isBusy" @click="photoInputEl?.click()">
            {{ PHOTO_LABELS[lang].pick }}
          </button>
          <button type="button" class="ai-actions__secondary" @click="isPhotoPanelOpen = false">
            {{ LEAD_LABELS[lang].cancel }}
          </button>
        </div>
        <input ref="photoInputEl" type="file" accept="image/*" class="ai-photo__input" @change="onPhotoPicked" />
      </div>

      <div v-if="isSlotPanelOpen" ref="slotPanelEl" class="ai-sheet ai-slots" tabindex="-1">
        <p class="ai-sheet__note">
          {{ bookingMode === 'calendar' ? APPOINTMENT_LABELS[lang].titleCalendar : APPOINTMENT_LABELS[lang].title }}
        </p>
        <p v-if="slotsState === 'loading'" class="ai-sheet__note">{{ APPOINTMENT_LABELS[lang].loading }}</p>
        <p v-else-if="slotsState === 'error'" class="ai-sheet__note">{{ APPOINTMENT_LABELS[lang].error }}</p>
        <template v-else-if="bookingMode === 'calendar'">
          <div
            v-if="appointmentKinds.length > 0"
            class="ai-slots__kinds"
            role="group"
            :aria-label="APPOINTMENT_LABELS[lang].kind"
          >
            <span class="ai-slots__label">{{ APPOINTMENT_LABELS[lang].kind }}</span>
            <button
              v-for="kind in appointmentKinds"
              :key="kind"
              type="button"
              class="ai-slots__chip"
              :aria-pressed="chosenKind === kind"
              @click="chosenKind = kind"
            >
              {{ kind }}
            </button>
          </div>
          <p v-if="slotTimes.length === 0" class="ai-sheet__note">{{ APPOINTMENT_LABELS[lang].none }}</p>
          <ul v-else class="ai-slots__list">
            <li v-for="time in slotTimes" :key="time.start">
              <button
                type="button"
                class="ai-slots__time"
                :aria-pressed="chosenTime?.start === time.start"
                @click="chosenTime = time"
              >
                {{ timeLabel(time.start) }}
              </button>
            </li>
          </ul>
          <div class="ai-slots__pages">
            <button v-if="slotsAfter !== null" type="button" class="ai-slots__more" @click="loadSlots(null)">
              {{ APPOINTMENT_LABELS[lang].first }}
            </button>
            <button v-if="hasMoreTimes" type="button" class="ai-slots__more" @click="showMoreTimes">
              {{ APPOINTMENT_LABELS[lang].more }}
            </button>
          </div>
        </template>
        <p v-else-if="slotDays.length === 0" class="ai-sheet__note">{{ APPOINTMENT_LABELS[lang].none }}</p>
        <ul v-else class="ai-slots__days">
          <li v-for="day in slotDays" :key="day.date" class="ai-slots__day">
            <span class="ai-slots__date">{{ dayLabel(day.date) }}</span>
            <button
              v-for="period in DAY_PERIODS"
              :key="period"
              type="button"
              class="ai-slots__slot"
              :disabled="!day.periods.includes(period)"
              :aria-pressed="isChosen(day.date, period)"
              :aria-label="slotLabel({ date: day.date, period })"
              @click="toggleSlot(day.date, period)"
            >
              {{ APPOINTMENT_LABELS[lang].periods[period] }}
            </button>
          </li>
        </ul>
        <div class="ai-actions">
          <button type="button" class="ai-actions__primary" :disabled="!canContinue" @click="confirmSlots">
            {{ APPOINTMENT_LABELS[lang].next }}
          </button>
          <button type="button" class="ai-actions__secondary" @click="closeSlotPanel">
            {{ LEAD_LABELS[lang].cancel }}
          </button>
        </div>
      </div>

      <div v-if="!leadSent && !isSlotPanelOpen && !isPhotoPanelOpen" class="ai-book">
        <button v-if="!showLeadForm" type="button" class="ai-book__open" @click="openLeadForm">
          {{ LEAD_LABELS[lang].open }}
        </button>
        <form v-else class="ai-leadform" @submit.prevent="submitLead">
          <p class="ai-leadform__title">{{ LEAD_LABELS[lang].title }}</p>
          <p v-if="chosenSlots.length > 0" class="ai-leadform__note">
            {{ APPOINTMENT_LABELS[lang].chosen }} : {{ chosenSlotsLine }}
          </p>
          <p v-else-if="chosenTime" class="ai-leadform__note">
            {{ APPOINTMENT_LABELS[lang].appointment }} : {{ chosenTimeLine }}
          </p>
          <input
            ref="leadNameEl"
            v-model="leadName"
            class="ai-leadform__field"
            maxlength="255"
            autocomplete="name"
            :placeholder="LEAD_LABELS[lang].name"
            :aria-label="LEAD_LABELS[lang].name"
          />
          <input
            v-model="leadContact"
            class="ai-leadform__field"
            maxlength="255"
            autocomplete="tel"
            :placeholder="LEAD_LABELS[lang].contact"
            :aria-label="LEAD_LABELS[lang].contact"
          />
          <input
            v-model="leadNeed"
            class="ai-leadform__field"
            maxlength="2000"
            autocomplete="off"
            :placeholder="LEAD_LABELS[lang].need"
            :aria-label="LEAD_LABELS[lang].need"
          />
          <div class="ai-leadform__row">
            <button
              type="submit"
              class="ai-leadform__send"
              :disabled="isSubmittingLead || !leadName.trim() || !leadContact.trim()"
            >
              {{ LEAD_LABELS[lang].send }}
            </button>
            <button type="button" class="ai-leadform__cancel" @click="cancelLeadForm">
              {{ LEAD_LABELS[lang].cancel }}
            </button>
          </div>
        </form>
      </div>

      <form class="ai-compose" @submit.prevent="send">
        <button
          type="button"
          class="ai-compose__tool"
          :aria-label="PHOTO_LABELS[lang].button"
          :title="PHOTO_LABELS[lang].button"
          :disabled="isBusy || photosRemaining <= 0"
          @click="openPhotoPanel"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
            <circle cx="12" cy="13" r="3" />
          </svg>
        </button>
        <button
          type="button"
          class="ai-compose__tool"
          :aria-label="APPOINTMENT_LABELS[lang].button"
          :title="APPOINTMENT_LABELS[lang].button"
          :disabled="isBusy || leadSent"
          @click="openSlotPanel"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="3.5" y="5" width="17" height="15" rx="2" />
            <path d="M3.5 10h17M8 3v4M16 3v4" />
          </svg>
        </button>
        <textarea
          v-model="draft"
          rows="1"
          maxlength="2000"
          :placeholder="UI_PLACEHOLDER[lang]"
          aria-label="Votre message"
          @keydown.enter.exact.prevent="send"
        />
        <button type="submit" class="ai-compose__send" aria-label="Envoyer" :disabled="isBusy || !draft.trim()">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M22 2 11 13" />
            <path d="M22 2 15 22l-4-9-9-4 20-7z" />
          </svg>
        </button>
      </form>
    </section>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import type { AssistantChatProps } from '~/types/AssistantChat'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import {
  APPOINTMENT_LABELS,
  DATE_LOCALES,
  FALLBACK_REPLY,
  GREETINGS,
  LANGUAGE_LABELS,
  LANGUAGE_NAMES,
  LEAD_LABELS,
  PHOTO_LABELS,
  SUGGESTIONS,
  UI_PLACEHOLDER,
} from '~/constants/AssistantWidgetLabels'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantPersonaUtils } from '~/utils/AssistantPersonaUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { MessageLinkUtils } from '~/utils/MessageLinkUtils'
import { PhotoCompressionUtils } from '~/utils/PhotoCompressionUtils'

const DEFAULT_LANG: AssistantWidgetLang = 'fr'
// Below this viewport width the panel goes full screen and the launcher drops its bubble.
const MOBILE_MAX_WIDTH: number = 560
// Below this viewport height too (a phone held sideways): the panel would not fit beside the page.
const MOBILE_MAX_HEIGHT: number = 640
// Distance from the launcher to the viewport edge (mirrors the CSS) and room for its shadow.
const LAUNCHER_EDGE_MARGIN: number = 22
const LAUNCHER_SHADOW_ALLOWANCE: number = 12
// Keep a returning visitor's conversation across page reloads, bounded so storage never grows unchecked.
const MAX_STORED_MESSAGES: number = 40
// Photos a visitor may send for one quote request (the API enforces the same quota per session).
const MAX_PHOTOS: number = 3

const DAY_PERIODS: AssistantDayPeriod[] = ['morning', 'afternoon']
// Every targeted country (FR, BE, LU, CH) keeps Paris time: slots always read in the business's time.
const BUSINESS_TIME_ZONE: string = 'Europe/Paris'

/**
 * The chat widget for a prospect's AI assistant, embedded on the demo page.
 * @param config Public assistant configuration returned by the API.
 */
const props: AssistantChatProps = defineProps({
  config: {
    type: Object as PropType<AiAssistantConfig>,
    required: true,
  },
})

const runtimeConfig: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
const publicEndpoint: ComputedRef<string> = computed(
  (): string => `${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${props.config.slug}`,
)

const isOpen: Ref<boolean> = ref(false)
const isBusy: Ref<boolean> = ref(false)
const draft: Ref<string> = ref('')
const lang: Ref<AssistantWidgetLang> = ref(DEFAULT_LANG)
const messages: Ref<AssistantChatMessage[]> = ref([])
// Random id sent with every turn so the server journal groups this visitor's conversation.
const sessionId: Ref<string> = ref('')
const messagesEl: Ref<HTMLElement | null> = ref(null)
const showLeadForm: Ref<boolean> = ref(false)
const leadSent: Ref<boolean> = ref(false)
const isSubmittingLead: Ref<boolean> = ref(false)
const leadName: Ref<string> = ref('')
const leadContact: Ref<string> = ref('')
const leadNeed: Ref<string> = ref('')
const launcherEl: Ref<HTMLElement | null> = ref(null)
const isPhotoPanelOpen: Ref<boolean> = ref(false)
const isSlotPanelOpen: Ref<boolean> = ref(false)
const slotPanelEl: Ref<HTMLElement | null> = ref(null)
const leadNameEl: Ref<HTMLInputElement | null> = ref(null)
const slotsState: Ref<AssistantSlotsState> = ref('idle')
const slotDays: Ref<AssistantAppointmentDay[]> = ref([])
const maxChosenSlots: Ref<number> = ref(2)
const chosenSlots: Ref<AssistantSlotChoice[]> = ref([])
const bookingMode: Ref<AssistantBookingMode> = ref('request')
const slotTimes: Ref<AssistantAppointmentTime[]> = ref([])
const hasMoreTimes: Ref<boolean> = ref(false)
// The last slot of the page before (null on the first page of free slots).
const slotsAfter: Ref<string | null> = ref(null)
const appointmentKinds: Ref<string[]> = ref([])
const chosenTime: Ref<AssistantAppointmentTime | null> = ref(null)
const chosenKind: Ref<string | null> = ref(null)
// The panel opens by itself at most once per visit, when the visitor asks the chat for an appointment.
const hasOfferedBooking: Ref<boolean> = ref(false)
const photoInputEl: Ref<HTMLInputElement | null> = ref(null)
const photosRemaining: Ref<number> = ref(MAX_PHOTOS)
// Thumbnail of each photo sent in this visit, by message index — kept out of the stored conversation.
const photoPreviews: Ref<Record<number, string>> = ref({})
const isEmbedded: Ref<boolean> = ref(false)
const viewportWidth: Ref<number | null> = ref(null)
const viewportHeight: Ref<number | null> = ref(null)
const closeEl: Ref<HTMLButtonElement | null> = ref(null)
let launcherObserver: ResizeObserver | null = null

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => {
  const palette: AssistantAccentPalette = AssistantAccentUtils.palette(props.config.accent_color)
  return { '--ai-accent': palette.accent, '--ai-accent-ink': palette.ink, '--ai-accent-text': palette.text }
})
const offeredLanguages: ComputedRef<AssistantWidgetLang[]> = computed((): AssistantWidgetLang[] => {
  const codes: AssistantWidgetLang[] = props.config.languages.filter(
    (code: string): code is AssistantWidgetLang => code in LANGUAGE_LABELS,
  )
  return codes.length ? codes : [DEFAULT_LANG]
})
const languagesLine: ComputedRef<string> = computed(
  (): string =>
    `Répond en ${offeredLanguages.value.map((code: AssistantWidgetLang): string => LANGUAGE_NAMES[code]).join(' · ')}`,
)
const roleLabel: ComputedRef<string> = computed((): string =>
  AssistantPersonaUtils.roleLabel(props.config.assistant_gender),
)
const suggestions: ComputedRef<string[]> = computed((): string[] => SUGGESTIONS[lang.value])
const chosenSlotsLine: ComputedRef<string> = computed((): string =>
  chosenSlots.value.map((slot: AssistantSlotChoice): string => slotLabel(slot)).join(' · '),
)
const chosenTimeLine: ComputedRef<string> = computed((): string => {
  if (!chosenTime.value) return ''
  const when: string = timeLabel(chosenTime.value.start)
  return chosenKind.value ? `${when} (${chosenKind.value})` : when
})
const canContinue: ComputedRef<boolean> = computed((): boolean =>
  bookingMode.value === 'calendar'
    ? chosenTime.value !== null && (appointmentKinds.value.length === 0 || chosenKind.value !== null)
    : chosenSlots.value.length > 0,
)
// The same rule as the loader: a narrow or a short viewport gets the full screen.
const isMobileLayout: ComputedRef<boolean> = computed(
  (): boolean =>
    (viewportWidth.value !== null && viewportWidth.value < MOBILE_MAX_WIDTH) ||
    (viewportHeight.value !== null && viewportHeight.value < MOBILE_MAX_HEIGHT),
)

/** Open the panel, greet the visitor once, and move the keyboard focus inside. */
function open(): void {
  isOpen.value = true
  if (!messages.value.length) {
    captureDemoEvent('assistant_opened')
    messages.value.push({ role: 'assistant', content: GREETINGS[lang.value] })
  }
  void nextTick((): void => closeEl.value?.focus())
}

/** Close the panel and give the keyboard focus back to the launcher. */
function close(): void {
  isOpen.value = false
  void nextTick((): void => launcherEl.value?.focus())
}

/** Show the contact form for a call back: an appointment picked before is not part of it. */
function openLeadForm(): void {
  forgetPicks()
  showLeadForm.value = true
  void nextTick((): void => leadNameEl.value?.focus())
}

/**
 * The visitor's browser language, when the assistant offers it, so the greeting and suggestions
 * open in their own language (they can still switch, and the chat always replies in their language).
 * @returns The matching offered language, or null when none of the visitor's languages is offered.
 */
function detectPreferredLang(): AssistantWidgetLang | null {
  if (typeof navigator === 'undefined') return null
  const offered: AssistantWidgetLang[] = offeredLanguages.value
  const wanted: string[] = [navigator.language, ...(navigator.languages ?? [])]
  for (const raw of wanted) {
    const code: string = raw.slice(0, 2).toLowerCase()
    const match: AssistantWidgetLang | undefined = offered.find((offer: AssistantWidgetLang): boolean => offer === code)
    if (match) return match
  }
  return null
}

/** The per-assistant localStorage key holding this visitor's conversation. */
function storageKey(): string {
  return `dlh-assistant-${props.config.slug}`
}

/**
 * Whether a value is a well-formed chat message (guards against corrupted stored data).
 * @param value A parsed entry from storage.
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
    const raw: string | null = localStorage.getItem(storageKey())
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
      storageKey(),
      JSON.stringify({
        lang: lang.value,
        sessionId: sessionId.value,
        messages: messages.value.slice(-MAX_STORED_MESSAGES),
      }),
    )
  } catch {
    // Storage unavailable (private mode) or full: the widget keeps working from memory.
  }
}

/**
 * Switch the widget's preset language (the assistant still replies in the visitor's own language).
 * @param code The language code to switch to.
 */
function setLang(code: AssistantWidgetLang): void {
  lang.value = code
  const greeting: AssistantChatMessage | undefined = messages.value[0]
  if (messages.value.length === 1 && greeting?.role === 'assistant') {
    greeting.content = GREETINGS[code]
  }
}

/**
 * Scroll the message list to its latest entry.
 * @returns A promise resolving once the DOM has updated.
 */
async function scrollToLatest(): Promise<void> {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

/**
 * Send a specific text as the visitor's message (an internal visit is flagged so it stays out of the counts).
 * @param text The message to send.
 * @returns A promise resolving once the reply is handled.
 */
async function sendText(text: string): Promise<void> {
  const trimmed: string = text.trim()
  if (!trimmed || isBusy.value) {
    return
  }
  messages.value.push({ role: 'user', content: trimmed })
  captureDemoEvent('assistant_message_sent')
  draft.value = ''
  isBusy.value = true
  await scrollToLatest()
  let offerBooking: boolean = false
  try {
    const answer: AssistantChatReply = await $fetch<AssistantChatReply>(`${publicEndpoint.value}/chat`, {
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
    await scrollToLatest()
  }
  if (offerBooking && !hasOfferedBooking.value && !showLeadForm.value) await openSlotPanel()
}

/**
 * Send the current draft as the visitor's message.
 * @returns A promise resolving once the reply is handled.
 */
async function send(): Promise<void> {
  await sendText(draft.value)
}

/** Show the photo panel: its privacy note comes before the file picker. */
function openPhotoPanel(): void {
  if (photosRemaining.value <= 0 || isBusy.value) return
  isSlotPanelOpen.value = false
  isPhotoPanelOpen.value = true
  void scrollToLatest()
}

/**
 * Show the appointment panel and load what it offers: the agenda's free slots, or open half-days (once per visit).
 * @returns A promise resolved once the offer is shown (or its failure).
 */
async function openSlotPanel(): Promise<void> {
  if (isBusy.value || leadSent.value) return
  hasOfferedBooking.value = true
  isPhotoPanelOpen.value = false
  isSlotPanelOpen.value = true
  void scrollToLatest()
  // The chip that opened it disappears: keyboard focus moves into the panel.
  await nextTick()
  slotPanelEl.value?.focus()
  // Free slots change: the agenda's are read again, from the first page, at each opening.
  if (slotsState.value !== 'ready' || bookingMode.value === 'calendar') await loadSlots()
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
      `${publicEndpoint.value}/appointment-slots`,
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
 * Replace the free slots shown by the next ones.
 * @returns A promise resolved once they are loaded.
 */
async function showMoreTimes(): Promise<void> {
  const last: AssistantAppointmentTime | undefined = slotTimes.value[slotTimes.value.length - 1]
  if (!last) return
  await loadSlots(last.start)
}

/**
 * Whether a half-day is among the visitor's picks.
 * @param date - The ISO day.
 * @param period - The half-day.
 * @returns True when picked.
 */
function isChosen(date: string, period: AssistantDayPeriod): boolean {
  return chosenSlots.value.some((slot: AssistantSlotChoice): boolean => slot.date === date && slot.period === period)
}

/**
 * Pick or drop a half-day; past the maximum, the oldest pick makes room.
 * @param date - The ISO day.
 * @param period - The half-day.
 */
function toggleSlot(date: string, period: AssistantDayPeriod): void {
  if (isChosen(date, period)) {
    chosenSlots.value = chosenSlots.value.filter(
      (slot: AssistantSlotChoice): boolean => slot.date !== date || slot.period !== period,
    )
    return
  }
  chosenSlots.value = [...chosenSlots.value, { date, period }].slice(-maxChosenSlots.value)
}

/**
 * Move on to the contact form with the picked half-days.
 * @returns A promise resolved once the name field has the focus.
 */
async function confirmSlots(): Promise<void> {
  if (!canContinue.value) return
  isSlotPanelOpen.value = false
  showLeadForm.value = true
  void scrollToLatest()
  await nextTick()
  leadNameEl.value?.focus()
}

/** Close the appointment panel and forget the picks. */
function closeSlotPanel(): void {
  isSlotPanelOpen.value = false
  forgetPicks()
}

/** Close the contact form; an appointment's picks go with it. */
function cancelLeadForm(): void {
  showLeadForm.value = false
  forgetPicks()
}

/** Forget the half-days, the free slot and the kind picked. */
function forgetPicks(): void {
  chosenSlots.value = []
  chosenTime.value = null
  chosenKind.value = null
}

/**
 * A free slot in the widget language and the business's time (« mar. 22 sept., 10:00 »).
 * @param iso - The slot's start, ISO with its offset.
 * @returns The short localized day and time.
 */
function timeLabel(iso: string): string {
  const format: Intl.DateTimeFormat = new Intl.DateTimeFormat(DATE_LOCALES[lang.value], {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: BUSINESS_TIME_ZONE,
  })
  return format.format(new Date(iso))
}

/**
 * A day in the widget language (« ven. 25 sept. »).
 * @param date - The ISO day.
 * @returns The short localized day.
 */
function dayLabel(date: string): string {
  const format: Intl.DateTimeFormat = new Intl.DateTimeFormat(DATE_LOCALES[lang.value], {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
  return format.format(new Date(`${date}T12:00:00`))
}

/**
 * A picked half-day in the widget language, as said in a sentence (« ven. 25 sept., matin »).
 * @param slot - The pick.
 * @returns Its label.
 */
function slotLabel(slot: AssistantSlotChoice): string {
  return `${dayLabel(slot.date)}, ${APPOINTMENT_LABELS[lang.value].periodsInline[slot.period]}`
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
 * Send the picked photo: shown at once as a thumbnail, described by the assistant, then the contact
 * form opens prefilled so the quote request can go out. The photo itself never enters the stored
 * conversation (only a « photo sent » line does).
 * @param event - The file input's change event.
 * @returns A promise resolved once the assistant has answered.
 */
async function onPhotoPicked(event: Event): Promise<void> {
  const input: HTMLInputElement = event.target as HTMLInputElement
  const file: File | undefined = input.files?.[0]
  input.value = ''
  isPhotoPanelOpen.value = false
  if (!file || isBusy.value) return
  if (!PhotoCompressionUtils.isPhoto(file)) {
    messages.value.push({ role: 'assistant', content: PHOTO_LABELS[lang.value].invalid })
    await scrollToLatest()
    return
  }
  // Busy from the start: a second photo picked while this one compresses would slip past the quota.
  isBusy.value = true
  const upload: Blob = await PhotoCompressionUtils.prepare(file)
  if (upload.size > PhotoCompressionUtils.MAX_BYTES) {
    isBusy.value = false
    messages.value.push({ role: 'assistant', content: PHOTO_LABELS[lang.value].tooLarge })
    await scrollToLatest()
    return
  }
  messages.value.push({ role: 'user', content: PHOTO_LABELS[lang.value].sent })
  const previewIndex: number = messages.value.length - 1
  const previewUrl: string = URL.createObjectURL(upload)
  photoPreviews.value = { ...photoPreviews.value, [previewIndex]: previewUrl }
  captureDemoEvent('assistant_photo_sent')
  await scrollToLatest()
  try {
    const form: FormData = new FormData()
    form.append('file', upload, 'photo.jpg')
    form.append('session_id', sessionId.value)
    form.append('language', lang.value)
    form.append('internal', String(DemoBeaconUtils.isInternalVisit()))
    const answer: AssistantPhotoReply = await $fetch<AssistantPhotoReply>(`${publicEndpoint.value}/photo`, {
      method: 'POST',
      body: form,
    })
    messages.value.push({ role: 'assistant', content: answer.reply })
    photosRemaining.value = answer.remaining
    if (answer.accepted && !leadSent.value) {
      if (!leadNeed.value.trim() && answer.need) leadNeed.value = answer.need
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
    await scrollToLatest()
  }
}

/**
 * Submit the visitor's contact details: the API turns them into a request tied to this conversation.
 * An internal visit (the owner testing) is sent as such so it is recorded without alerting anyone.
 *
 * @returns A promise resolved once the request is sent.
 */
async function submitLead(): Promise<void> {
  if (isSubmittingLead.value || !leadName.value.trim() || !leadContact.value.trim()) return
  isSubmittingLead.value = true
  const booking: AssistantAppointmentTime | null = bookingMode.value === 'calendar' ? chosenTime.value : null
  try {
    const reply: AssistantLeadReply = await $fetch<AssistantLeadReply>(`${publicEndpoint.value}/lead`, {
      method: 'POST',
      body: {
        name: leadName.value,
        contact: leadContact.value,
        need: leadNeed.value,
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
    await scrollToLatest()
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
    await scrollToLatest()
  } finally {
    isSubmittingLead.value = false
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
    const when: string = timeLabel(reply.booked_start)
    const booked: string = labels.booked.replace('{slots}', chosenKind.value ? `${when} (${chosenKind.value})` : when)
    if (reply.confirmation_channel === 'sms') return booked + labels.bookedSms
    if (reply.confirmation_channel === 'email') return booked + labels.bookedEmail
    return booked
  }
  if (booking) return labels.sent.replace('{slots}', timeLabel(booking.start))
  if (chosenSlots.value.length > 0) return labels.sent.replace('{slots}', chosenSlotsLine.value)
  return LEAD_LABELS[lang.value].sent
}

/**
 * Tell the loader iframe how big to be: the launcher's exact footprint when closed, the panel when open.
 */
function postFrameSize(): void {
  if (!isEmbedded.value) return
  const launcher: HTMLElement | null = launcherEl.value
  if (isOpen.value || !launcher) {
    window.parent.postMessage({ type: 'dlh-assistant-resize', open: isOpen.value }, '*')
    return
  }
  const footprint: DOMRect = launcher.getBoundingClientRect()
  window.parent.postMessage(
    {
      type: 'dlh-assistant-resize',
      open: false,
      width: footprint.width + LAUNCHER_EDGE_MARGIN + LAUNCHER_SHADOW_ALLOWANCE,
      height: footprint.height + LAUNCHER_EDGE_MARGIN + LAUNCHER_SHADOW_ALLOWANCE,
    },
    '*',
  )
}

/**
 * Read the host page's viewport width posted by the loader, so the layout follows the client's screen.
 * @param event - A message received from the parent window.
 */
function onHostMessage(event: MessageEvent): void {
  // Only the page that frames the widget may size it: another frame of the host page may not.
  if (event.source !== window.parent) return
  const data: Record<string, unknown> | null = typeof event.data === 'object' ? event.data : null
  if (!data || data.type !== 'dlh-assistant-host' || typeof data.width !== 'number' || data.width <= 0) return
  viewportWidth.value = data.width
  viewportHeight.value = typeof data.height === 'number' && data.height > 0 ? data.height : null
}

/** Follow the page's own viewport when the widget runs on the demo page rather than in an iframe. */
function readOwnViewport(): void {
  viewportWidth.value = window.innerWidth
  viewportHeight.value = window.innerHeight
}

// Opening/closing and the mobile switch (bubble shown or hidden) both change the footprint to report.
watch([isOpen, isMobileLayout], (): void => {
  void nextTick(postFrameSize)
})

// The launcher is re-created each time the panel closes: measure it whenever it (re)appears or reflows.
watch(launcherEl, (launcher: HTMLElement | null): void => {
  launcherObserver?.disconnect()
  if (launcher && launcherObserver) launcherObserver.observe(launcher)
})

/**
 * A random id for this visitor's conversation (the browser's UUID when available).
 * @returns The new session id.
 */
function newSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

// Restore a returning visitor's conversation; otherwise open in their browser language when offered.
onMounted((): void => {
  const restored: boolean = restoreConversation()
  if (!restored) {
    const preferred: AssistantWidgetLang | null = detectPreferredLang()
    if (preferred) lang.value = preferred
  }
  if (!sessionId.value) sessionId.value = newSessionId()
  isEmbedded.value = window.parent !== window
  if (isEmbedded.value) {
    window.addEventListener('message', onHostMessage)
    if (typeof ResizeObserver !== 'undefined') {
      launcherObserver = new ResizeObserver((): void => postFrameSize())
      if (launcherEl.value) launcherObserver.observe(launcherEl.value)
    }
    window.parent.postMessage({ type: 'dlh-assistant-ready' }, '*')
    void nextTick(postFrameSize)
    return
  }
  readOwnViewport()
  window.addEventListener('resize', readOwnViewport)
})

onBeforeUnmount((): void => {
  Object.values(photoPreviews.value).forEach((url: string): void => URL.revokeObjectURL(url))
  window.removeEventListener('message', onHostMessage)
  window.removeEventListener('resize', readOwnViewport)
  launcherObserver?.disconnect()
})

// Keep the stored conversation in step with what the visitor sees.
watch([messages, lang], (): void => persistConversation(), { deep: true })
</script>

<style scoped>
.ai-widget {
  --ai-paper: #f7f3ec;
  --ai-paper-2: #fbf9f3;
  --ai-card: #fffdf9;
  --ai-ink: #17130d;
  --ai-ink-dim: #6d665b;
  --ai-line: rgba(23, 19, 13, 0.14);
  --ai-line-soft: rgba(23, 19, 13, 0.07);
  --ai-font-d: 'Fraunces', Georgia, serif;
  --ai-font-b: 'Inter', system-ui, sans-serif;
  font-family: var(--ai-font-b);
  color: var(--ai-ink);
}

.ai-launcher {
  position: fixed;
  right: max(22px, env(safe-area-inset-right, 0px));
  bottom: max(22px, env(safe-area-inset-bottom, 0px));
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 13px;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
}
.ai-launcher__say {
  background: var(--ai-card);
  color: var(--ai-ink);
  border: 1px solid var(--ai-line);
  border-radius: 14px;
  padding: 10px 15px;
  font-size: 0.85rem;
  line-height: 1.4;
  max-width: 220px;
  text-align: left;
  box-shadow: 0 24px 60px -28px rgba(23, 19, 13, 0.35);
}
.ai-launcher__say strong {
  font-family: var(--ai-font-d);
  font-weight: 600;
}
.ai-launcher__orb {
  width: 60px;
  height: 60px;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 10px 28px -12px rgba(23, 19, 13, 0.5);
}

.ai-panel {
  position: fixed;
  right: max(22px, env(safe-area-inset-right, 0px));
  bottom: max(22px, env(safe-area-inset-bottom, 0px));
  z-index: 60;
  width: 392px;
  max-width: calc(100vw - 28px);
  height: min(628px, calc(100vh - 44px));
  background: var(--ai-paper-2);
  border: 1px solid var(--ai-line);
  border-radius: 22px;
  box-shadow: 0 34px 80px -34px rgba(23, 19, 13, 0.55);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ai-head {
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 13px;
}
.ai-head__av {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  overflow: hidden;
  flex: none;
  box-shadow: 0 2px 8px rgba(23, 19, 13, 0.18);
}
.ai-head__who {
  flex: 1;
  min-width: 0;
}
.ai-head__who b {
  font-family: var(--ai-font-d);
  font-size: 1.12rem;
  font-weight: 600;
  display: block;
}
.ai-head__who span {
  font-size: 0.74rem;
  opacity: 0.82;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ai-head__x {
  margin-left: auto;
  background: rgba(244, 239, 230, 0.14);
  border: 0;
  color: var(--ai-accent-ink);
  width: 32px;
  height: 32px;
  border-radius: 10px;
  cursor: pointer;
  flex: none;
}
.ai-sub {
  margin: 0;
  background: var(--ai-accent);
  filter: brightness(1.12);
  color: var(--ai-accent-ink);
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-align: center;
  padding: 5px;
  opacity: 0.92;
}
.ai-langs {
  display: flex;
  gap: 6px;
  padding: 11px 15px 5px;
  flex-wrap: wrap;
  background: var(--ai-paper-2);
}
.ai-langs button {
  border: 1px solid var(--ai-line);
  background: var(--ai-paper-2);
  color: var(--ai-ink-dim);
  font: inherit;
  font-size: 0.74rem;
  padding: 7px 12px;
  border-radius: 999px;
  cursor: pointer;
}
.ai-langs button[aria-pressed='true'] {
  border-color: var(--ai-accent);
  color: var(--ai-accent-text);
}
.ai-msgs {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 11px;
  background: var(--ai-paper-2);
}
.ai-m {
  max-width: 85%;
  padding: 11px 14px;
  font-size: 0.92rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
  border-radius: 15px;
}
.ai-m--assistant {
  background: var(--ai-card);
  color: var(--ai-ink);
  align-self: flex-start;
  border: 1px solid var(--ai-line-soft);
  border-bottom-left-radius: 5px;
}
.ai-m--user {
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
  align-self: flex-end;
  border-bottom-right-radius: 5px;
}
/* A page of the business's site given in a reply: a plain link that wraps anywhere. */
.ai-m__link {
  color: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
  overflow-wrap: anywhere;
}
.ai-typing {
  align-self: flex-start;
  display: flex;
  gap: 4px;
  padding: 13px 15px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line-soft);
  border-radius: 15px;
  border-bottom-left-radius: 5px;
}
.ai-typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ai-ink-dim);
  animation: ai-blink 1.1s infinite;
}
.ai-typing i:nth-child(2) {
  animation-delay: 0.18s;
}
.ai-typing i:nth-child(3) {
  animation-delay: 0.36s;
}
@keyframes ai-blink {
  0%,
  60%,
  100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 0.9;
    transform: translateY(-3px);
  }
}
.ai-chips {
  display: flex;
  gap: 7px;
  padding: 5px 15px;
  flex-wrap: wrap;
  background: var(--ai-paper-2);
}
.ai-chips button {
  border: 1px solid var(--ai-line);
  background: var(--ai-card);
  color: var(--ai-ink);
  font: inherit;
  font-size: 0.78rem;
  padding: 7px 12px;
  border-radius: 999px;
  cursor: pointer;
  text-align: left;
}
.ai-chips button:hover {
  border-color: var(--ai-accent);
  color: var(--ai-accent-text);
}
.ai-chips__action {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ai-chips__icon {
  flex: none;
}
/* Bounded in the panel: on a short screen the form scrolls, the conversation keeps its room. */
.ai-book {
  flex: 0 1 auto;
  min-height: 0;
  max-height: 68%;
  overflow-y: auto;
  padding: 4px 15px 10px;
  background: var(--ai-paper-2);
}
.ai-book__open {
  width: 100%;
  border: 1px solid var(--ai-line);
  background: var(--ai-card);
  color: var(--ai-ink);
  font: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  padding: 10px;
  border-radius: 12px;
  cursor: pointer;
}
.ai-book__open:hover {
  border-color: var(--ai-accent);
  color: var(--ai-accent-text);
}
.ai-leadform {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line-soft);
  border-radius: 14px;
  padding: 13px;
}
.ai-leadform__title {
  margin: 0;
  font-family: var(--ai-font-d);
  font-size: 0.95rem;
  font-weight: 600;
}
.ai-leadform__field {
  border: 1px solid var(--ai-line);
  border-radius: 10px;
  padding: 9px 11px;
  font: inherit;
  /* 16px minimum: stops iOS Safari from zooming the page on focus. */
  font-size: 16px;
  background: var(--ai-paper-2);
  color: var(--ai-ink);
}
.ai-leadform__field:focus {
  outline: 2px solid var(--ai-accent);
  outline-offset: 1px;
}
.ai-leadform__row,
.ai-actions {
  display: flex;
  gap: 8px;
}
.ai-leadform__send,
.ai-leadform__cancel,
.ai-actions__primary,
.ai-actions__secondary {
  flex: 1;
  border: 0;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.ai-leadform__send,
.ai-actions__primary {
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
}
.ai-leadform__send:disabled,
.ai-actions__primary:disabled {
  opacity: 0.45;
  cursor: default;
}
.ai-leadform__cancel,
.ai-actions__secondary {
  background: transparent;
  color: var(--ai-ink-dim);
  border: 1px solid var(--ai-line);
}
.ai-compose {
  display: flex;
  gap: 9px;
  padding: 12px 15px;
  border-top: 1px solid var(--ai-line-soft);
  background: var(--ai-paper-2);
  align-items: flex-end;
}
.ai-compose textarea {
  flex: 1;
  resize: none;
  border: 1px solid var(--ai-line);
  border-radius: 13px;
  padding: 11px 13px;
  font: inherit;
  /* 16px minimum: below it, iOS Safari zooms the whole page when the field is focused. */
  font-size: 16px;
  background: var(--ai-card);
  color: var(--ai-ink);
  max-height: 96px;
  min-height: 44px;
  line-height: 1.4;
}
/* An empty field keeps its hint on one line, however narrow the bar is beside its tool buttons. */
.ai-compose textarea:placeholder-shown {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ai-compose textarea:focus {
  outline: 2px solid var(--ai-accent);
  outline-offset: 1px;
}
.ai-compose__tool {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  border: 1px solid var(--ai-line);
  background: var(--ai-card);
  color: var(--ai-ink);
  cursor: pointer;
  display: grid;
  place-items: center;
}
.ai-compose__tool:hover {
  border-color: var(--ai-accent);
  color: var(--ai-accent-text);
}
.ai-compose__tool:disabled {
  opacity: 0.45;
  cursor: default;
}
.ai-sheet {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 4px 15px 10px;
  padding: 13px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line-soft);
  border-radius: 14px;
}
.ai-sheet__note,
.ai-leadform__note {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--ai-ink-dim);
}
.ai-photo__input {
  display: none;
}
/* Bounded in the panel: the days scroll, the note and the buttons stay in view. */
.ai-slots {
  flex: 0 1 auto;
  min-height: 0;
  max-height: 64%;
}
.ai-slots__days,
.ai-slots__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
  overflow-y: auto;
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
/* Tall enough to tap: at least 36 px on a phone. */
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
  border-color: var(--ai-accent);
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
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
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.ai-slots__time[aria-pressed='true'] {
  border-color: var(--ai-accent);
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
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
.ai-m--photo {
  padding: 4px;
}
.ai-m__photo {
  display: block;
  max-width: 180px;
  max-height: 180px;
  border-radius: 11px;
  object-fit: cover;
}
.ai-compose__send {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  border: 0;
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
  cursor: pointer;
  display: grid;
  place-items: center;
}
.ai-compose__send:disabled {
  opacity: 0.45;
  cursor: default;
}
.ai-panel--mobile {
  right: 0;
  bottom: 0;
  width: 100vw;
  max-width: 100vw;
  height: 100dvh;
  border-radius: 0;
  border: 0;
}
.ai-launcher--mobile .ai-launcher__say {
  display: none;
}
@media (prefers-reduced-motion: reduce) {
  .ai-typing i {
    animation: none;
  }
}
</style>
