<template>
  <div class="ai-widget" :style="accentStyle">
    <button
      v-if="!isOpen"
      type="button"
      class="ai-launcher"
      :aria-label="`Ouvrir ${config.assistant_name}`"
      @click="open"
    >
      <span class="ai-launcher__say">
        Une question&nbsp;? <strong>{{ config.assistant_name }}</strong> vous répond, 24h/24.
      </span>
      <span class="ai-launcher__orb" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path
            d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 8.5-8.5 8.38 8.38 0 0 1 8.5 8.5z"
          />
        </svg>
      </span>
    </button>

    <section v-else class="ai-panel" :aria-label="config.assistant_name">
      <header class="ai-head">
        <span class="ai-head__av">{{ assistantInitial }}</span>
        <span class="ai-head__who">
          <b>{{ config.assistant_name }}</b>
          <span>Assistante {{ config.business_name }} · en ligne</span>
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
        <div v-for="(message, index) in messages" :key="index" class="ai-m" :class="`ai-m--${message.role}`">
          {{ message.content }}
        </div>
        <div v-if="isBusy" class="ai-typing" aria-label="Rédaction en cours"><i /><i /><i /></div>
      </div>

      <div v-if="messages.length <= 1" class="ai-chips">
        <button v-for="suggestion in suggestions" :key="suggestion" type="button" @click="sendText(suggestion)">
          {{ suggestion }}
        </button>
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
import { computed, nextTick, ref } from 'vue'
import type {
  AiAssistantConfig,
  AssistantChatMessage,
  AssistantChatReply,
  AssistantLeadLabels,
  AssistantWidgetLang,
} from '~/types/AiAssistant'
import type { AssistantChatProps } from '~/types/AssistantChat'

const DEFAULT_LANG: AssistantWidgetLang = 'fr'
const FALLBACK_ACCENT: string = '#a9793f'

const LANGUAGE_LABELS: Record<AssistantWidgetLang, string> = {
  fr: 'Français',
  en: 'English',
  de: 'Deutsch',
  lu: 'Lëtzebuergesch',
}
const LANGUAGE_NAMES: Record<AssistantWidgetLang, string> = {
  fr: 'français',
  en: 'English',
  de: 'Deutsch',
  lu: 'Lëtzebuergesch',
}
const GREETINGS: Record<AssistantWidgetLang, string> = {
  fr: 'Bonjour et bienvenue. Comment puis-je vous aider ?',
  en: 'Hello and welcome. How can I help you?',
  de: 'Guten Tag und willkommen. Wie kann ich Ihnen helfen?',
  lu: 'Moien a wëllkomm. Wéi kann ech Iech hëllefen?',
}
const SUGGESTIONS: Record<AssistantWidgetLang, string[]> = {
  fr: ['Quels sont vos horaires ?', 'Quels services proposez-vous ?', 'Je souhaite être recontacté'],
  en: ['What are your opening hours?', 'What services do you offer?', "I'd like to be contacted"],
  de: ['Wie sind Ihre Öffnungszeiten?', 'Welche Leistungen bieten Sie an?', 'Ich möchte zurückgerufen werden'],
  lu: ['Wéi sinn Är Ëffnungszäiten?', 'Wéi eng Servicer bitt Dir un?', 'Ech wëll zréckgeruff ginn'],
}
const UI_PLACEHOLDER: Record<AssistantWidgetLang, string> = {
  fr: 'Écrivez votre message…',
  en: 'Type your message…',
  de: 'Ihre Nachricht…',
  lu: 'Är Noriicht…',
}
const FALLBACK_REPLY: Record<AssistantWidgetLang, string> = {
  fr: 'Désolée, je rencontre un souci technique. Réessayez dans un instant.',
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
const messagesEl: Ref<HTMLElement | null> = ref(null)
const showLeadForm: Ref<boolean> = ref(false)
const leadSent: Ref<boolean> = ref(false)
const isSubmittingLead: Ref<boolean> = ref(false)
const leadName: Ref<string> = ref('')
const leadContact: Ref<string> = ref('')
const leadNeed: Ref<string> = ref('')

const accentStyle: ComputedRef<Record<string, string>> = computed(() => ({
  '--ai-accent': props.config.accent_color || FALLBACK_ACCENT,
}))
const assistantInitial: ComputedRef<string> = computed(() =>
  (props.config.assistant_name.trim()[0] || 'A').toUpperCase(),
)
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
const suggestions: ComputedRef<string[]> = computed(() => SUGGESTIONS[lang.value])

/** Open the panel and greet the visitor once. */
function open(): void {
  isOpen.value = true
  if (!messages.value.length) {
    messages.value.push({ role: 'assistant', content: GREETINGS[lang.value] })
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
 * Send a specific text as the visitor's message.
 * @param text The message to send.
 * @returns A promise resolving once the reply is handled.
 */
async function sendText(text: string): Promise<void> {
  const trimmed: string = text.trim()
  if (!trimmed || isBusy.value) {
    return
  }
  messages.value.push({ role: 'user', content: trimmed })
  draft.value = ''
  isBusy.value = true
  await scrollToLatest()
  try {
    const answer: AssistantChatReply = await $fetch<AssistantChatReply>(
      `${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${props.config.slug}/chat`,
      { method: 'POST', body: { messages: messages.value } },
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

/**
 * Submit the visitor's contact details as a qualified lead.
 *
 * @returns A promise resolved once the lead is sent.
 */
async function submitLead(): Promise<void> {
  if (isSubmittingLead.value || !leadName.value.trim() || !leadContact.value.trim()) return
  isSubmittingLead.value = true
  try {
    await $fetch(`${runtimeConfig.public.apiBase}/api/v1/ai-assistants/public/${props.config.slug}/lead`, {
      method: 'POST',
      body: { name: leadName.value, contact: leadContact.value, need: leadNeed.value, language: lang.value },
    })
    leadSent.value = true
    showLeadForm.value = false
    messages.value.push({ role: 'assistant', content: LEAD_UI[lang.value].sent })
    await scrollToLatest()
  } catch {
    messages.value.push({ role: 'assistant', content: FALLBACK_REPLY[lang.value] })
  } finally {
    isSubmittingLead.value = false
  }
}
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
  border-radius: 18px;
  background: var(--ai-accent);
  color: var(--ai-accent-ink);
  display: grid;
  place-items: center;
  box-shadow: 0 10px 28px -12px rgba(23, 19, 13, 0.5);
}
.ai-launcher__orb svg {
  width: 27px;
  height: 27px;
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
  background: var(--ai-accent-ink);
  color: var(--ai-accent);
  display: grid;
  place-items: center;
  font-family: var(--ai-font-d);
  font-size: 1.3rem;
  font-weight: 600;
  flex: none;
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
  font-size: 0.88rem;
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
  font-size: 0.92rem;
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
@media (max-width: 560px) {
  .ai-panel {
    right: 0;
    bottom: 0;
    width: 100vw;
    max-width: 100vw;
    height: 100dvh;
    border-radius: 0;
    border: 0;
  }
  .ai-launcher__say {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ai-typing i {
    animation: none;
  }
}
</style>
