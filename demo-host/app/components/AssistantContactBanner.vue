<template>
  <div v-if="isVisible" class="ac" :class="{ 'ac--open': state !== 'collapsed' }" :style="accentStyle">
    <!-- Collapsed pill — bottom-left so it never covers the assistant widget (bottom-right). -->
    <button v-if="state === 'collapsed'" type="button" class="ac-pill" @click="open">
      <img v-if="ownerPhotoUrl" class="ac-avatar" :src="ownerPhotoUrl" alt="" />
      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true">
        <path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1" stroke-linecap="round" />
      </svg>
      <span class="ac-pill__text">
        <span class="ac-pill__label">Cet assistant vous plaît ?</span>
        <span class="ac-pill__hint">Écrivez-moi un mot</span>
      </span>
    </button>

    <!-- Open card — one optional message; the visit came from an email, so no coordinates asked. -->
    <div v-else-if="state === 'open'" class="ac-card">
      <div class="ac-card__head">
        <span class="ac-card__title">Parler à {{ ownerName || 'la personne qui vous l’a envoyé' }}</span>
        <button type="button" class="ac-card__close" aria-label="Réduire" @click="collapse">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
      <p class="ac-card__intro">
        Intéressé par l’assistant de {{ businessName }} ? Laissez-moi un mot, je reviens vers vous.
      </p>
      <textarea
        v-model="message"
        class="ac-card__field"
        rows="3"
        placeholder="Votre message (facultatif)"
        aria-label="Votre message"
      />
      <button type="button" class="ac-card__send" :disabled="isSending" @click="submit">
        {{ isSending ? 'Envoi…' : 'Envoyer' }}
      </button>
      <p v-if="hasError" class="ac-card__error">Envoi impossible, réessayez dans un instant.</p>
      <div v-if="hasOwnerContact" class="ac-card__contacts">
        <a v-if="ownerPhone" class="ac-chip" :href="ownerPhoneHref">Appeler</a>
        <a v-if="ownerEmail" class="ac-chip" :href="ownerEmailHref">Écrire un email</a>
      </div>
    </div>

    <!-- Sent confirmation. -->
    <div v-else class="ac-card ac-card--sent">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
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
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'

const FALLBACK_ACCENT: string = '#a9793f'

/**
 * « Cet assistant vous plaît ? » banner overlaid on the assistant sales page (/ia/{slug}).
 * Lets the prospect (the business owner) raise their hand towards the seller — a hot buy signal,
 * beaconed to the assistant interest endpoint which notifies the owner in real time.
 * @param slug The assistant's public slug.
 * @param businessName The prospect's business name, shown in the card.
 * @param ownerName The seller's name, shown in the card title.
 * @param ownerPhotoUrl The seller's photo URL, shown in the pill.
 * @param ownerPhone The seller's phone, for the direct « Appeler » chip.
 * @param ownerEmail The seller's email, for the direct email chip.
 * @param status The assistant status — the banner shows only on an active assistant.
 * @param accentColor The prospect's brand accent, used on the send button.
 */
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
  '--ac-accent': props.accentColor || FALLBACK_ACCENT,
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
.ac {
  position: fixed;
  bottom: 18px;
  left: 18px;
  z-index: 40;
  font-family: 'Inter', system-ui, sans-serif;
}
.ac-pill {
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
.ac-pill svg {
  width: 15px;
  height: 15px;
  color: var(--ac-accent);
  flex-shrink: 0;
}
.ac-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.ac-pill__text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
  text-align: left;
  min-width: 0;
}
.ac-pill__label {
  font-size: 0.82rem;
  font-weight: 600;
}
.ac-pill__hint {
  font-size: 0.72rem;
  color: #6d665b;
}
.ac-card {
  width: min(320px, 82vw);
  padding: 16px;
  border: 1px solid rgba(23, 19, 13, 0.1);
  border-radius: 16px;
  background: #fffdf8;
  box-shadow: 0 12px 34px rgba(23, 19, 13, 0.18);
  color: #17130d;
}
.ac-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.ac-card__title {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1rem;
  font-weight: 600;
}
.ac-card__close {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  color: #a09a8c;
  cursor: pointer;
}
.ac-card__close svg {
  width: 16px;
  height: 16px;
}
.ac-card__intro {
  margin: 0 0 10px;
  font-size: 0.82rem;
  line-height: 1.45;
  color: #6d665b;
}
.ac-card__field {
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
.ac-card__field:focus {
  outline: none;
  border-color: var(--ac-accent);
}
.ac-card__send {
  width: 100%;
  margin-top: 10px;
  padding: 10px;
  border: none;
  border-radius: 10px;
  background: var(--ac-accent);
  color: #fff;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.ac-card__send:disabled {
  opacity: 0.6;
  cursor: default;
}
.ac-card__error {
  margin: 8px 0 0;
  font-size: 0.76rem;
  color: #9f3a2f;
}
.ac-card__contacts {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(23, 19, 13, 0.08);
}
.ac-chip {
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
.ac-card--sent {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  line-height: 1.4;
  color: #17130d;
}
.ac-card--sent svg {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  color: var(--ac-accent);
}
@media (max-width: 560px) {
  .ac {
    bottom: 14px;
    left: 14px;
  }
  .ac-pill__hint {
    display: none;
  }
}
</style>
