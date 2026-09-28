<template>
  <div
    v-if="isVisible"
    class="contact-banner"
    :class="{ 'contact-banner--open': state !== 'collapsed' }"
    :style="accentStyle"
  >
    <!-- Collapsed pill, bottom-left so it never covers the assistant widget (bottom-right). -->
    <button v-if="state === 'collapsed'" type="button" class="contact-banner__pill" @click="open">
      <img v-if="ownerPhotoUrl" class="contact-banner__avatar" :src="ownerPhotoUrl" alt="" />
      <svg
        v-else
        class="contact-banner__pill-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.4"
        aria-hidden="true"
      >
        <path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1" stroke-linecap="round" />
      </svg>
      <span class="contact-banner__pill-text">
        <span class="contact-banner__pill-label">Votre réceptionniste vous plaît ?</span>
        <span class="contact-banner__pill-hint">Écrivez-moi un mot</span>
      </span>
    </button>

    <!-- The visit came from an email: one optional message, no contact details asked. -->
    <div v-else-if="state === 'open'" class="contact-banner__card">
      <div class="contact-banner__card-head">
        <span class="contact-banner__card-title"> Parler à {{ ownerName || 'la personne qui vous l’a envoyé' }} </span>
        <button type="button" class="contact-banner__card-close" aria-label="Réduire" @click="collapse">
          <svg
            class="contact-banner__card-close-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
      <p class="contact-banner__card-intro">
        Votre réceptionniste pour {{ businessName }} vous intéresse ? Laissez-moi un mot, je reviens vers vous.
      </p>
      <textarea
        v-model="message"
        class="contact-banner__card-field"
        rows="3"
        placeholder="Votre message (facultatif)"
        aria-label="Votre message"
      />
      <button type="button" class="contact-banner__card-send" :disabled="isSending" @click="submit">
        {{ isSending ? 'Envoi…' : 'Envoyer' }}
      </button>
      <p v-if="hasError" class="contact-banner__card-error">Envoi impossible, réessayez dans un instant.</p>
      <div v-if="hasOwnerContact" class="contact-banner__card-contacts">
        <a v-if="ownerPhone" class="contact-banner__contact-link" :href="ownerPhoneHref">Appeler</a>
        <a v-if="ownerEmail" class="contact-banner__contact-link" :href="ownerEmailHref">Écrire un email</a>
      </div>
    </div>

    <div v-else class="contact-banner__card contact-banner__card--sent">
      <svg
        class="contact-banner__sent-icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <p>Merci, votre message est envoyé. On vous recontacte très vite.</p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import { computed, onMounted, ref } from 'vue'
import type { AssistantContactBannerProps, AssistantContactBannerState } from '~/types/AssistantContactBanner'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'

const props: AssistantContactBannerProps = defineProps({
  slug: { type: String, required: true },
  businessName: { type: String, required: true },
  ownerName: { type: String as PropType<string | null>, default: null },
  ownerPhotoUrl: { type: String as PropType<string | null>, default: null },
  ownerPhone: { type: String as PropType<string | null>, default: null },
  ownerEmail: { type: String as PropType<string | null>, default: null },
  status: { type: String, required: true },
  accentColor: { type: String as PropType<string | null>, default: null },
})

const runtimeConfig: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()

const state: Ref<AssistantContactBannerState> = ref('collapsed')
const message: Ref<string> = ref('')
const isSending: Ref<boolean> = ref(false)
const hasError: Ref<boolean> = ref(false)
/** Client-only flag: the visibility guards need `window`. */
const isClientReady: Ref<boolean> = ref(false)

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--contact-banner-accent': props.accentColor || AssistantAccentUtils.FALLBACK_ACCENT,
}))

const ownerPhotoUrl: ComputedRef<string> = computed((): string => (props.ownerPhotoUrl ?? '').trim())
const ownerPhone: ComputedRef<string> = computed((): string => (props.ownerPhone ?? '').trim())
const ownerEmail: ComputedRef<string> = computed((): string => (props.ownerEmail ?? '').trim())
const ownerName: ComputedRef<string> = computed((): string => (props.ownerName ?? '').trim())

const ownerPhoneHref: ComputedRef<string> = computed((): string => `tel:${ownerPhone.value.replace(/[^+\d]/g, '')}`)
const ownerEmailHref: ComputedRef<string> = computed((): string => `mailto:${ownerEmail.value}`)
const hasOwnerContact: ComputedRef<boolean> = computed(
  (): boolean => Boolean(ownerPhone.value) || Boolean(ownerEmail.value),
)

/** Whether the banner renders at all — active assistants, real prospect visits, never embedded. */
const isVisible: ComputedRef<boolean> = computed((): boolean => {
  if (!isClientReady.value) return false
  if (props.status !== 'active') return false
  if (DemoBeaconUtils.isInternalVisit()) return false
  return window.self === window.top
})

const apiBase: ComputedRef<string> = computed((): string => String(runtimeConfig.public.apiBase ?? ''))

/** Open the message card from the collapsed pill. */
function open(): void {
  state.value = 'open'
}

/** Reduce the card back to the pill (the banner is never fully closed). */
function collapse(): void {
  state.value = 'collapsed'
}

/**
 * Beacon the prospect's interest (message optional) to the assistant interest endpoint.
 * @returns A promise resolved once the beacon is attempted.
 */
async function submit(): Promise<void> {
  if (isSending.value) return
  isSending.value = true
  hasError.value = false
  try {
    const response: Response = await fetch(`${apiBase.value}/api/v1/ai-assistants/public/${props.slug}/interest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message.value.trim() || null }),
    })
    if (!response.ok) throw new Error(`interest beacon failed (${response.status})`)
    state.value = 'sent'
  } catch {
    hasError.value = true
  } finally {
    isSending.value = false
  }
}

onMounted((): void => {
  isClientReady.value = true
})
</script>

<style scoped>
.contact-banner {
  position: fixed;
  bottom: 18px;
  left: 18px;
  z-index: 40;
  font-family: 'Inter', system-ui, sans-serif;
}
.contact-banner__pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: 78vw;
  padding: 9px 14px 9px 10px;
  border: 1px solid rgba(23, 19, 13, 0.1);
  border-radius: 999px;
  background: #fffdf8;
  box-shadow: 0 8px 24px rgba(23, 19, 13, 0.14);
  cursor: pointer;
  color: #17130d;
}
.contact-banner__pill-icon {
  width: 15px;
  height: 15px;
  color: var(--contact-banner-accent);
  flex-shrink: 0;
}
.contact-banner__avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.contact-banner__pill-text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  text-align: left;
  min-width: 0;
}
.contact-banner__pill-label {
  font-size: 0.82rem;
  font-weight: 600;
}
.contact-banner__pill-hint {
  font-size: 0.72rem;
  color: #6d665b;
}
.contact-banner__card {
  width: min(320px, 82vw);
  padding: 16px;
  border: 1px solid rgba(23, 19, 13, 0.1);
  border-radius: 16px;
  background: #fffdf8;
  box-shadow: 0 12px 34px rgba(23, 19, 13, 0.18);
  color: #17130d;
}
.contact-banner__card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.contact-banner__card-title {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1rem;
  font-weight: 600;
}
.contact-banner__card-close {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: #a09a8c;
  cursor: pointer;
}
.contact-banner__card-close-icon {
  width: 16px;
  height: 16px;
}
.contact-banner__card-intro {
  margin: 0 0 10px;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #6d665b;
}
.contact-banner__card-field {
  width: 100%;
  padding: 9px 11px;
  border: 1px solid rgba(23, 19, 13, 0.14);
  border-radius: 10px;
  font: inherit;
  font-size: 0.85rem;
  color: #17130d;
  background: #fff;
  resize: vertical;
  box-sizing: border-box;
}
.contact-banner__card-field:focus {
  outline: none;
  border-color: var(--contact-banner-accent);
}
.contact-banner__card-send {
  width: 100%;
  margin-top: 10px;
  padding: 10px;
  border: none;
  border-radius: 10px;
  background: var(--contact-banner-accent);
  color: #fff;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.contact-banner__card-send:disabled {
  opacity: 0.6;
  cursor: default;
}
.contact-banner__card-error {
  margin: 8px 0 0;
  font-size: 0.76rem;
  color: #9f3a2f;
}
.contact-banner__card-contacts {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(23, 19, 13, 0.08);
}
.contact-banner__contact-link {
  flex: 1;
  padding: 8px;
  border: 1px solid rgba(23, 19, 13, 0.14);
  border-radius: 9px;
  text-align: center;
  font-size: 0.78rem;
  font-weight: 500;
  color: #17130d;
  text-decoration: none;
}
.contact-banner__card--sent {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  line-height: 1.4;
  color: #17130d;
}
.contact-banner__sent-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  color: var(--contact-banner-accent);
}
@media (max-width: 560px) {
  .contact-banner {
    bottom: 14px;
    left: 14px;
  }
  .contact-banner__pill-hint {
    display: none;
  }
}
</style>
