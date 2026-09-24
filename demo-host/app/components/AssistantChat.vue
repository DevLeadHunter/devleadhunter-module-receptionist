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
      :aria-label="config.assistant_name"
    >
      <header class="ai-head">
        <span class="ai-head__av"><AssistantAvatar /></span>
        <span class="ai-head__who">
          <b>{{ config.assistant_name }}</b>
          <span>{{ roleLabel }} {{ config.business_name }} · en ligne</span>
        </span>
        <button type="button" class="ai-head__x" aria-label="Fermer" @click="isOpen = false">✕</button>
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

      <div ref="messagesEl" class="ai-msgs">
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="ai-m"
          :class="[`ai-m--${message.role}`, { 'ai-m--photo': photoPreviews[index] }]"
        >
          <img v-if="photoPreviews[index]" :src="photoPreviews[index]" :alt="message.content" class="ai-m__photo" />
          <template v-else>{{ message.content }}</template>
        </div>
        <div v-if="isBusy" class="ai-typing" aria-label="Rédaction en cours"><i /><i /><i /></div>
      </div>

      <div v-if="messages.length <= 1" class="ai-chips">
        <button type="button" @click="openPhotoPanel">{{ PHOTO_UI[lang].chip }}</button>
        <button v-for="suggestion in suggestions" :key="suggestion" type="button" @click="sendText(suggestion)">
          {{ suggestion }}
        </button>
      </div>

      <div v-if="isPhotoPanelOpen" class="ai-photo">
        <p class="ai-photo__note">{{ PHOTO_UI[lang].note }}</p>
        <div class="ai-leadform__row">
          <button type="button" class="ai-leadform__send" :disabled="isBusy" @click="photoInputEl?.click()">
            {{ PHOTO_UI[lang].pick }}
          </button>
          <button type="button" class="ai-leadform__cancel" @click="isPhotoPanelOpen = false">
            {{ LEAD_UI[lang].cancel }}
          </button>
        </div>
        <input ref="photoInputEl" type="file" accept="image/*" class="ai-photo__input" @change="onPhotoPicked" />
      </div>

      <div v-if="!leadSent" class="ai-book">
        <button v-if="!showLeadForm" type="button" class="ai-book__open" @click="showLeadForm = true">
          {{ LEAD_UI[lang].open }}
        </button>
        <form v-else class="ai-leadform" @submit.prevent="submitLead">
          <p class="ai-leadform__title">{{ LEAD_UI[lang].title }}</p>
          <input v-model="leadName" class="ai-leadform__field" :placeholder="LEAD_UI[lang].name" />
          <input v-model="leadContact" class="ai-leadform__field" :placeholder="LEAD_UI[lang].contact" />
          <input v-model="leadNeed" class="ai-leadform__field" :placeholder="LEAD_UI[lang].need" />
          <div class="ai-leadform__row">
            <button
              type="submit"
              class="ai-leadform__send"
              :disabled="isSubmittingLead || !leadName.trim() || !leadContact.trim()"
            >
              {{ LEAD_UI[lang].send }}
            </button>
            <button type="button" class="ai-leadform__cancel" @click="showLeadForm = false">
              {{ LEAD_UI[lang].cancel }}
            </button>
          </div>
        </form>
      </div>

      <form class="ai-compose" @submit.prevent="send">
        <button
          type="button"
          class="ai-compose__photo"
          :aria-label="PHOTO_UI[lang].button"
          :title="PHOTO_UI[lang].button"
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
        <textarea
          v-model="draft"
          rows="1"
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
  AssistantChatMessage,
  AssistantChatReply,
  AssistantLeadLabels,
  AssistantPhotoLabels,
  AssistantPhotoReply,
  AssistantWidgetLang,
} from '~/types/AiAssistant'
import type { AssistantChatProps } from '~/types/AssistantChat'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { AssistantPersonaUtils } from '~/utils/AssistantPersonaUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { PhotoCompressionUtils } from '~/utils/PhotoCompressionUtils'

const DEFAULT_LANG: AssistantWidgetLang = 'fr'
const FALLBACK_ACCENT: string = '#a9793f'
// Below this viewport width the panel goes full screen and the launcher drops its bubble.
const MOBILE_MAX_WIDTH: number = 560
// Distance from the launcher to the viewport edge (mirrors the CSS) and room for its shadow.
const LAUNCHER_EDGE_MARGIN: number = 22
const LAUNCHER_SHADOW_ALLOWANCE: number = 12
// Keep a returning visitor's conversation across page reloads, bounded so storage never grows unchecked.
const MAX_STORED_MESSAGES: number = 40
// Photos a visitor may send for one quote request (the API enforces the same quota per session).
const MAX_PHOTOS: number = 3

const LANGUAGE_LABELS: Record<AssistantWidgetLang, string> = {
  fr: 'Français',
  nl: 'Nederlands',
  en: 'English',
  de: 'Deutsch',
  lu: 'Lëtzebuergesch',
}
const LANGUAGE_NAMES: Record<AssistantWidgetLang, string> = {
  fr: 'français',
  nl: 'Nederlands',
  en: 'English',
  de: 'Deutsch',
  lu: 'Lëtzebuergesch',
}
const GREETINGS: Record<AssistantWidgetLang, string> = {
  fr: 'Bonjour et bienvenue. Comment puis-je vous aider ?',
  nl: 'Hallo en welkom. Hoe kan ik u helpen?',
  en: 'Hello and welcome. How can I help you?',
  de: 'Guten Tag und willkommen. Wie kann ich Ihnen helfen?',
  lu: 'Moien a wëllkomm. Wéi kann ech Iech hëllefen?',
}
const SUGGESTIONS: Record<AssistantWidgetLang, string[]> = {
  fr: ['Quels sont vos horaires ?', 'Quels services proposez-vous ?', 'Je souhaite être recontacté'],
  nl: ['Wat zijn jullie openingstijden?', 'Welke diensten bieden jullie aan?', 'Ik wil graag teruggebeld worden'],
  en: ['What are your opening hours?', 'What services do you offer?', "I'd like to be contacted"],
  de: ['Wie sind Ihre Öffnungszeiten?', 'Welche Leistungen bieten Sie an?', 'Ich möchte zurückgerufen werden'],
  lu: ['Wéi sinn Är Ëffnungszäiten?', 'Wéi eng Servicer bitt Dir un?', 'Ech wëll zréckgeruff ginn'],
}
const UI_PLACEHOLDER: Record<AssistantWidgetLang, string> = {
  fr: 'Écrivez votre message…',
  nl: 'Typ uw bericht…',
  en: 'Type your message…',
  de: 'Ihre Nachricht…',
  lu: 'Är Noriicht…',
}
const FALLBACK_REPLY: Record<AssistantWidgetLang, string> = {
  fr: 'Je rencontre un souci technique. Réessayez dans un instant.',
  nl: 'Sorry, er is een technisch probleem. Probeer het zo meteen opnieuw.',
  en: 'Sorry, I hit a technical issue. Please try again in a moment.',
  de: 'Entschuldigung, es gab ein technisches Problem. Bitte versuchen Sie es gleich erneut.',
  lu: 'Pardon, et gouf e technescht Problem. Probéiert w.e.g. gläich nach eng Kéier.',
}
const LEAD_UI: Record<AssistantWidgetLang, AssistantLeadLabels> = {
  fr: {
    open: 'Être rappelé',
    title: 'Laissez vos coordonnées',
    name: 'Votre nom',
    contact: 'Email ou téléphone',
    need: 'Votre besoin (facultatif)',
    send: 'Envoyer',
    cancel: 'Annuler',
    sent: 'Merci, vos coordonnées sont transmises. On vous recontacte très vite.',
  },
  nl: {
    open: 'Word teruggebeld',
    title: 'Laat uw gegevens achter',
    name: 'Uw naam',
    contact: 'E-mail of telefoon',
    need: 'Wat u nodig heeft (optioneel)',
    send: 'Versturen',
    cancel: 'Annuleren',
    sent: 'Bedankt, uw gegevens zijn verzonden. We nemen snel contact met u op.',
  },
  en: {
    open: 'Request a callback',
    title: 'Leave your details',
    name: 'Your name',
    contact: 'Email or phone',
    need: 'What you need (optional)',
    send: 'Send',
    cancel: 'Cancel',
    sent: 'Thank you, your details have been sent. We will get back to you shortly.',
  },
  de: {
    open: 'Rückruf anfragen',
    title: 'Ihre Kontaktdaten',
    name: 'Ihr Name',
    contact: 'E-Mail oder Telefon',
    need: 'Ihr Anliegen (optional)',
    send: 'Senden',
    cancel: 'Abbrechen',
    sent: 'Danke, Ihre Daten wurden übermittelt. Wir melden uns in Kürze.',
  },
  lu: {
    open: 'Réckruff ufroen',
    title: 'Är Kontaktdaten',
    name: 'Ären Numm',
    contact: 'E-Mail oder Telefon',
    need: 'Wat Dir braucht (fakultativ)',
    send: 'Schécken',
    cancel: 'Ofbriechen',
    sent: 'Merci, Är Donnéeë sinn iwwerdroen. Mir mellen eis geschwënn.',
  },
}

const PHOTO_UI: Record<AssistantWidgetLang, AssistantPhotoLabels> = {
  fr: {
    chip: '📷 Envoyer une photo pour un devis',
    button: 'Envoyer une photo',
    note: "Votre photo sert uniquement à préparer votre devis et elle est supprimée au bout de 90 jours. Évitez d'y montrer des personnes.",
    pick: 'Choisir une photo',
    sent: '📷 Photo envoyée',
    invalid: 'Je ne peux pas lire ce fichier. Envoyez une photo au format JPEG ou PNG.',
    tooLarge: 'Cette photo est trop lourde (8 Mo maximum).',
    quota: "Vous avez déjà envoyé 3 photos : c'est suffisant pour préparer le devis.",
  },
  nl: {
    chip: '📷 Stuur een foto voor een offerte',
    button: 'Foto sturen',
    note: 'Uw foto dient alleen om uw offerte voor te bereiden en wordt na 90 dagen verwijderd. Zet er liefst geen personen op.',
    pick: 'Foto kiezen',
    sent: '📷 Foto verzonden',
    invalid: 'Ik kan dit bestand niet lezen. Stuur een foto in JPEG- of PNG-formaat.',
    tooLarge: 'Deze foto is te groot (max. 8 MB).',
    quota: "U hebt al 3 foto's gestuurd: dat volstaat voor de offerte.",
  },
  en: {
    chip: '📷 Send a photo for a quote',
    button: 'Send a photo',
    note: 'Your photo is only used to prepare your quote and is deleted after 90 days. Please avoid showing people.',
    pick: 'Choose a photo',
    sent: '📷 Photo sent',
    invalid: "I can't read this file. Please send a JPEG or PNG photo.",
    tooLarge: 'This photo is too large (8 MB max).',
    quota: "You've already sent 3 photos, that's enough to prepare the quote.",
  },
  de: {
    chip: '📷 Foto für ein Angebot senden',
    button: 'Foto senden',
    note: 'Ihr Foto dient nur zur Vorbereitung Ihres Angebots und wird nach 90 Tagen gelöscht. Bitte keine Personen zeigen.',
    pick: 'Foto auswählen',
    sent: '📷 Foto gesendet',
    invalid: 'Diese Datei kann ich nicht lesen. Bitte senden Sie ein JPEG- oder PNG-Foto.',
    tooLarge: 'Dieses Foto ist zu groß (max. 8 MB).',
    quota: 'Sie haben bereits 3 Fotos gesendet, das reicht für das Angebot.',
  },
  lu: {
    chip: '📷 Eng Foto fir en Devis schécken',
    button: 'Foto schécken',
    note: 'Är Foto déngt nëmme fir Ären Devis virzebereeden a gëtt no 90 Deeg geläscht. Weist w.e.g. keng Persounen drop.',
    pick: 'Foto auswielen',
    sent: '📷 Foto geschéckt',
    invalid: 'Ech kann dëse Fichier net liesen. Schéckt w.e.g. eng JPEG- oder PNG-Foto.',
    tooLarge: 'Dës Foto ass ze grouss (max. 8 MB).',
    quota: 'Dir hutt schonn 3 Fotoe geschéckt, dat geet duer fir den Devis.',
  },
}

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
const photoInputEl: Ref<HTMLInputElement | null> = ref(null)
const photosRemaining: Ref<number> = ref(MAX_PHOTOS)
// Thumbnail of each photo sent in this visit, by message index — kept out of the stored conversation.
const photoPreviews: Ref<Record<number, string>> = ref({})
const isEmbedded: Ref<boolean> = ref(false)
const viewportWidth: Ref<number | null> = ref(null)
let launcherObserver: ResizeObserver | null = null

const accentStyle: ComputedRef<Record<string, string>> = computed(() => ({
  '--ai-accent': props.config.accent_color || FALLBACK_ACCENT,
}))
const offeredLanguages: ComputedRef<AssistantWidgetLang[]> = computed(() => {
  const codes: AssistantWidgetLang[] = props.config.languages.filter(
    (code: string): code is AssistantWidgetLang => code in LANGUAGE_LABELS,
  )
  return codes.length ? codes : [DEFAULT_LANG]
})
const languagesLine: ComputedRef<string> = computed(
  () =>
    `Répond en ${offeredLanguages.value.map((code: AssistantWidgetLang): string => LANGUAGE_NAMES[code]).join(' · ')}`,
)
const roleLabel: ComputedRef<string> = computed(() => AssistantPersonaUtils.roleLabel(props.config.assistant_gender))
const suggestions: ComputedRef<string[]> = computed(() => SUGGESTIONS[lang.value])
const isMobileLayout: ComputedRef<boolean> = computed(
  (): boolean => viewportWidth.value !== null && viewportWidth.value < MOBILE_MAX_WIDTH,
)

/** Open the panel and greet the visitor once. */
function open(): void {
  isOpen.value = true
  if (!messages.value.length) {
    captureDemoEvent('assistant_opened')
    messages.value.push({ role: 'assistant', content: GREETINGS[lang.value] })
  }
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
  if (typeof localStorage === 'undefined') return false
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
  if (typeof localStorage === 'undefined') return
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
  try {
    const answer: AssistantChatReply = await $fetch<AssistantChatReply>(
      `${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${props.config.slug}/chat`,
      {
        method: 'POST',
        body: {
          messages: messages.value,
          session_id: sessionId.value,
          language: lang.value,
          internal: DemoBeaconUtils.isInternalVisit(),
        },
      },
    )
    messages.value.push({ role: 'assistant', content: answer.reply })
  } catch {
    messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[lang.value] })
  } finally {
    isBusy.value = false
    await scrollToLatest()
  }
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
  isPhotoPanelOpen.value = true
  void scrollToLatest()
}

/**
 * The visitor-facing message for a photo the API refused (quota, size, format) or could not take.
 * @param error - What the upload threw.
 * @returns A message in the widget language.
 */
function photoErrorMessage(error: unknown): string {
  const status: number | undefined = (error as { statusCode?: number } | null)?.statusCode
  if (status === 409) {
    photosRemaining.value = 0
    return PHOTO_UI[lang.value].quota
  }
  if (status === 413) return PHOTO_UI[lang.value].tooLarge
  if (status === 415) return PHOTO_UI[lang.value].invalid
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
    messages.value.push({ role: 'assistant', content: PHOTO_UI[lang.value].invalid })
    await scrollToLatest()
    return
  }
  // Busy from the start: a second photo picked while this one compresses would slip past the quota.
  isBusy.value = true
  const upload: Blob = await PhotoCompressionUtils.prepare(file)
  if (upload.size > PhotoCompressionUtils.MAX_BYTES) {
    isBusy.value = false
    messages.value.push({ role: 'assistant', content: PHOTO_UI[lang.value].tooLarge })
    await scrollToLatest()
    return
  }
  messages.value.push({ role: 'user', content: PHOTO_UI[lang.value].sent })
  photoPreviews.value = { ...photoPreviews.value, [messages.value.length - 1]: URL.createObjectURL(upload) }
  captureDemoEvent('assistant_photo_sent')
  await scrollToLatest()
  try {
    const form: FormData = new FormData()
    form.append('file', upload, 'photo.jpg')
    form.append('session_id', sessionId.value)
    form.append('language', lang.value)
    form.append('internal', String(DemoBeaconUtils.isInternalVisit()))
    const answer: AssistantPhotoReply = await $fetch<AssistantPhotoReply>(
      `${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${props.config.slug}/photo`,
      { method: 'POST', body: form },
    )
    messages.value.push({ role: 'assistant', content: answer.reply })
    photosRemaining.value = answer.remaining
    if (answer.accepted && !leadSent.value) {
      if (!leadNeed.value.trim() && answer.need) leadNeed.value = answer.need
      showLeadForm.value = true
    }
  } catch (error: unknown) {
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
  try {
    await $fetch(`${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${props.config.slug}/lead`, {
      method: 'POST',
      body: {
        name: leadName.value,
        contact: leadContact.value,
        need: leadNeed.value,
        language: lang.value,
        session_id: sessionId.value,
        internal: DemoBeaconUtils.isInternalVisit(),
      },
    })
    leadSent.value = true
    captureDemoEvent('assistant_lead_submitted')
    showLeadForm.value = false
    messages.value.push({ role: 'assistant', content: LEAD_UI[lang.value].sent })
    await scrollToLatest()
  } catch {
    messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[lang.value] })
  } finally {
    isSubmittingLead.value = false
  }
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
  const data: Record<string, unknown> | null = typeof event.data === 'object' ? event.data : null
  if (!data || data.type !== 'dlh-assistant-host' || typeof data.width !== 'number' || data.width <= 0) return
  viewportWidth.value = data.width
}

/** Follow the page's own viewport when the widget runs on the demo page rather than in an iframe. */
function readOwnViewport(): void {
  viewportWidth.value = window.innerWidth
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
  --ai-accent-ink: #f4efe6;
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
  padding: 5px 11px;
  border-radius: 999px;
  cursor: pointer;
}
.ai-langs button[aria-pressed='true'] {
  border-color: var(--ai-accent);
  color: var(--ai-accent);
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
  color: var(--ai-accent);
}
.ai-book {
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
  color: var(--ai-accent);
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
.ai-leadform__row {
  display: flex;
  gap: 8px;
}
.ai-leadform__send,
.ai-leadform__cancel {
  flex: 1;
  border: 0;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.ai-leadform__send {
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
}
.ai-leadform__send:disabled {
  opacity: 0.45;
  cursor: default;
}
.ai-leadform__cancel {
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
.ai-compose textarea:focus {
  outline: 2px solid var(--ai-accent);
  outline-offset: 1px;
}
.ai-compose__photo {
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
.ai-compose__photo:hover {
  border-color: var(--ai-accent);
  color: var(--ai-accent);
}
.ai-compose__photo:disabled {
  opacity: 0.45;
  cursor: default;
}
.ai-photo {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 4px 15px 10px;
  padding: 13px;
  background: var(--ai-card);
  border: 1px solid var(--ai-line-soft);
  border-radius: 14px;
}
.ai-photo__note {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--ai-ink-dim);
}
.ai-photo__input {
  display: none;
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
