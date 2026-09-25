<template>
  <div v-if="pending" class="av av--message">Chargement…</div>
  <div v-else-if="!assistant || !assistant.video_available" class="av av--message av--error">
    Vidéo introuvable ou pas encore prête.
  </div>
  <main v-else class="av" :style="accentStyle">
    <div class="av__content">
      <p class="av__kicker">Assistant en ligne</p>
      <h1 class="av__title">
        L'assistant de <em>{{ shortBusinessName }}</em> vous répond<span class="av__accent-dot">.</span>
      </h1>
      <p class="av__lede">
        <template v-if="videoDurationSeconds">
          <strong>{{ videoDurationSeconds }} secondes</strong> pour le voir en action, puis parlez-lui vous-même.
        </template>
        <template v-else>Une courte vidéo pour le voir en action, puis parlez-lui vous-même.</template>
      </p>

      <div class="av__stage">
        <div class="av__frame">
          <video
            ref="playerRef"
            class="av__player"
            :src="assistant.video_url ?? ''"
            :poster="assistant.video_thumbnail_url ?? ''"
            playsinline
            preload="metadata"
            @loadedmetadata="readVideoDuration"
            @ended="showEndCard"
          />
          <button
            v-if="!hasStartedPlayback"
            type="button"
            class="av__overlay"
            aria-label="Lancer la vidéo"
            @click="startPlayback"
          >
            <span class="av__play av__pulse">
              <svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <polygon points="8 5 19 12 8 19" />
              </svg>
            </span>
            <span class="av__play-label">Lancer la démo{{ playLabelDurationSuffix }}</span>
          </button>
          <div
            class="av__endcard"
            :class="{ 'av__endcard--visible': isEndCardVisible }"
            :aria-hidden="isEndCardVisible ? 'false' : 'true'"
          >
            <h2 class="av__endcard-title">À vous de lui parler<span class="av__accent-dot">.</span></h2>
            <p class="av__endcard-text">Posez-lui une question : {{ subjectPronoun }} répond en quelques secondes.</p>
            <a class="av__cta" :href="demoHref" @click="trackCtaClick('endcard')">
              Essayer l'assistant
              <svg
                class="av__cta-icon"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M5 12h14" />
                <path d="m13 6 6 6-6 6" />
              </svg>
            </a>
            <button type="button" class="av__replay" @click="replayVideo">
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M3 12a9 9 0 1 0 3-6.7" />
                <path d="M3 4v5h5" />
              </svg>
              Revoir la vidéo
            </button>
          </div>
        </div>
      </div>

      <div class="av__cta-row" :class="{ 'av__cta-row--hidden': isEndCardVisible }">
        <a class="av__cta av__pulse" :href="demoHref" @click="trackCtaClick('page')">
          Essayer l'assistant
          <svg
            class="av__cta-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M5 12h14" />
            <path d="m13 6 6 6-6 6" />
          </svg>
        </a>
        <p class="av__cta-note">En ligne 24h/24 — parlez-lui vous-même.</p>
      </div>

      <AssistantContactBanner
        :slug="assistant.slug"
        :business-name="assistant.business_name"
        :owner-name="assistant.owner_name ?? null"
        :owner-photo-url="assistant.owner_profile_photo_url ?? null"
        :owner-phone="assistant.owner_contact_phone ?? null"
        :owner-email="assistant.owner_contact_email ?? null"
        :status="assistant.status"
        :accent-color="assistant.accent_color"
      />

      <p v-if="ownerNameLabel" class="av__signature">
        Assistant réalisé pour {{ shortBusinessName }} par {{ ownerNameLabel }}, développeur web
      </p>
    </div>
  </main>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, ref } from 'vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import { captureDemoEvent, useDemoTracking } from '~/composables/useDemoTracking'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantPersonaUtils } from '~/utils/AssistantPersonaUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'

const route: ReturnType<typeof useRoute> = useRoute()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
const slug: ComputedRef<string> = computed((): string => String(route.params.slug ?? ''))

const playerRef: Ref<HTMLVideoElement | null> = ref(null)
const videoDurationSeconds: Ref<number | null> = ref(null)
const hasStartedPlayback: Ref<boolean> = ref(false)
const isEndCardVisible: Ref<boolean> = ref(false)

const { data: assistant, pending }: Awaited<ReturnType<typeof useAsyncData<AiAssistantConfig | null | undefined>>> =
  await useAsyncData<AiAssistantConfig | null>(
    () => `assistant-video-${slug.value}`,
    async (): Promise<AiAssistantConfig | null> => {
      try {
        return await $fetch<AiAssistantConfig>(`${config.public.apiBase}/api/v1/ai-assistants/public/${slug.value}`)
      } catch {
        return null
      }
    },
  )

const shortBusinessName: ComputedRef<string> = computed((): string =>
  BusinessNameUtils.short(assistant.value?.business_name ?? ''),
)

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--av-accent': assistant.value?.accent_color || AssistantAccentUtils.FALLBACK_ACCENT,
}))

const playLabelDurationSuffix: ComputedRef<string> = computed((): string =>
  videoDurationSeconds.value ? ` — ${videoDurationSeconds.value} s` : '',
)

/** Link to try the live assistant (the /a/ demo page). */
const demoHref: ComputedRef<string> = computed((): string => `/ia/${slug.value}`)

/** Owner name for the signature line (empty when the owner set no name). */
const ownerNameLabel: ComputedRef<string> = computed((): string => (assistant.value?.owner_name ?? '').trim())

const subjectPronoun: ComputedRef<string> = computed((): string =>
  AssistantPersonaUtils.subjectPronoun(assistant.value?.assistant_gender),
)

/** Read the video duration once its metadata loads, so the page can display it. */
function readVideoDuration(): void {
  const seconds: number | undefined = playerRef.value?.duration
  if (seconds && Number.isFinite(seconds)) videoDurationSeconds.value = Math.round(seconds)
}

/** First play: drop the custom overlay, hand over to native controls and start the clip. */
function startPlayback(): void {
  hasStartedPlayback.value = true
  if (playerRef.value) {
    playerRef.value.controls = true
    void playerRef.value.play()
  }
  captureDemoEvent('assistant_video_play')
}

/** Clip ended: the end card relays the « essayer l'assistant » CTA at the moment of highest intent. */
function showEndCard(): void {
  isEndCardVisible.value = true
  if (playerRef.value) playerRef.value.controls = false
  captureDemoEvent('assistant_video_endcard_shown')
}

/** Replay the video from its start (from the end card). */
function replayVideo(): void {
  isEndCardVisible.value = false
  if (playerRef.value) {
    playerRef.value.controls = true
    playerRef.value.currentTime = 0
    void playerRef.value.play()
  }
}

/**
 * Track a click on the « essayer l'assistant » CTA (PostHog).
 * @param placement - Which CTA was clicked: 'page' (below the video) or 'endcard' (end of clip).
 */
function trackCtaClick(placement: 'page' | 'endcard'): void {
  captureDemoEvent('assistant_video_cta_click', { placement })
}

const { init: initTracking }: ReturnType<typeof useDemoTracking> = useDemoTracking()

onMounted((): void => {
  const current: AiAssistantConfig | null | undefined = assistant.value
  if (!current) return
  initTracking(current.slug, current.status, null, DemoBeaconUtils.channelFromQuery(route.query.src), 'assistant')
})

useHead({
  title: computed((): string => `${assistant.value?.business_name ?? 'Assistant'} — votre assistant en vidéo`),
})
</script>

<style scoped>
/* DevLeadHunter editorial DA; --av-accent is injected from the prospect's brand colour. */
.av {
  --av-paper: #f7f3ec;
  --av-ink: #17130d;
  --av-ink-dim: #6d665b;
  --av-line: rgba(23, 19, 13, 0.14);
  /* The stage halo (inset -9%) bled past narrow viewports (X scroll) — clip where it is transparent anyway. */
  overflow-x: clip;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--av-paper);
  color: var(--av-ink);
  font-family: Inter, system-ui, sans-serif;
}

.av--message {
  justify-content: center;
  font-size: 15px;
  color: var(--av-ink-dim);
}

.av--error {
  color: #9f3a2f;
}

.av :focus-visible {
  outline: 2px solid var(--av-accent);
  outline-offset: 3px;
  border-radius: 4px;
}

.av__content {
  width: 100%;
  max-width: 780px;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: clamp(40px, 8vh, 96px) 24px 40px;
}

/* ── Editorial header ──────────────────────────────────────────────────── */
.av__kicker {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--av-ink-dim);
}

.av__kicker::before {
  content: '';
  width: 26px;
  height: 2px;
  background: var(--av-accent);
}

.av__title {
  margin: 22px 0 0;
  font-family: Fraunces, Georgia, serif;
  font-weight: 600;
  font-size: clamp(34px, 6.4vw, 58px);
  line-height: 1.04;
  letter-spacing: -0.015em;
  color: var(--av-ink);
  text-wrap: balance;
}

.av__title em {
  font-style: italic;
  font-weight: 400;
}

.av__accent-dot {
  color: var(--av-accent);
}

.av__lede {
  margin: 20px 0 0;
  max-width: 54ch;
  font-size: clamp(15px, 2.2vw, 17px);
  line-height: 1.65;
  color: var(--av-ink-dim);
}

.av__lede strong {
  color: var(--av-ink);
  font-weight: 600;
}

/* ── Video: prospect-tinted wash + thin frame ──────────────────────────── */
.av__stage {
  position: relative;
  margin-top: clamp(28px, 5vh, 44px);
}

.av__stage::before {
  content: '';
  position: absolute;
  inset: -7% -9%;
  background: radial-gradient(closest-side, color-mix(in srgb, var(--av-accent) 16%, transparent), transparent 72%);
  z-index: 0;
  pointer-events: none;
}

.av__frame {
  position: relative;
  z-index: 1;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--av-line);
  box-shadow: 0 24px 60px -28px rgba(23, 19, 13, 0.35);
  background: #000;
}

.av__player {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

/* Hide the browser's big central play overlay so only our custom overlay shows before playback. */
.av__player::-webkit-media-controls-overlay-play-button {
  display: none;
}

.av__overlay {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  width: 100%;
  padding: 0;
  border: 0;
  background: linear-gradient(to top, rgba(23, 19, 13, 0.38), rgba(23, 19, 13, 0.06) 45%);
  cursor: pointer;
  transition: opacity 0.25s;
}

/* 14.4% = the circle baked into the thumbnail (184/1280) — the button covers it exactly. */
.av__play {
  width: 14.4%;
  min-width: 52px;
  aspect-ratio: 1;
  border-radius: 999px;
  background: var(--av-ink);
  color: var(--av-paper);
  display: grid;
  place-items: center;
  box-shadow: 0 14px 38px rgba(23, 19, 13, 0.4);
  transition: transform 0.18s;
}

.av__overlay:hover .av__play {
  transform: scale(1.07);
}

/* The glyph sits slightly right of centre — the optical nudge a play triangle needs. */
.av__play svg {
  display: block;
  width: 56%;
  height: auto;
}

.av__play-label {
  position: absolute;
  top: calc(62.8% + 12px);
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  font-size: 13px;
  font-weight: 500;
  color: var(--av-paper);
  background: rgba(23, 19, 13, 0.72);
  backdrop-filter: blur(6px);
  padding: 8px 16px;
  border-radius: 999px;
}

/* ── End card: the CTA at the moment of highest intent ─────────────────── */
.av__endcard {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  padding: 24px;
  background: rgba(247, 243, 236, 0.96);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition:
    opacity 0.4s,
    visibility 0.4s;
}

.av__endcard--visible {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
}

.av__endcard-title {
  margin: 0;
  font-family: Fraunces, Georgia, serif;
  font-weight: 600;
  font-size: clamp(22px, 4vw, 34px);
  line-height: 1.12;
  color: var(--av-ink);
}

.av__endcard-text {
  margin: 0 0 12px;
  font-size: 14.5px;
  color: var(--av-ink-dim);
}

.av__replay {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--av-ink-dim);
  font-size: 13px;
  cursor: pointer;
}

.av__replay:hover {
  color: var(--av-ink);
}

/* ── CTA: black pill, the DA's signature shape ─────────────────────────── */
.av__cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px 32px;
  border-radius: 999px;
  background: var(--av-ink);
  color: var(--av-paper);
  font-weight: 600;
  font-size: 15.5px;
  text-decoration: none;
  box-shadow: 0 10px 28px -12px rgba(23, 19, 13, 0.5);
  transition:
    transform 0.15s,
    box-shadow 0.15s;
}

.av__cta-icon {
  flex: none;
  transition: transform 0.18s;
}

.av__cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 34px -12px rgba(23, 19, 13, 0.55);
}

.av__cta:hover .av__cta-icon {
  transform: translateX(3px);
}

/* Same layout on every viewport: full-width pill, note centered below. */
.av__cta-row {
  margin-top: clamp(26px, 4vh, 38px);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
  transition:
    opacity 0.35s,
    visibility 0.35s;
}

.av__cta-row--hidden {
  animation: none;
  opacity: 0;
  visibility: hidden;
}

.av__cta-note {
  margin: 0;
  font-size: 13.5px;
  color: var(--av-ink-dim);
  text-align: center;
}

/* ── Owner signature ───────────────────────────────────────────────────── */
.av__signature {
  margin-top: auto;
  padding-top: clamp(40px, 8vh, 72px);
  font-size: 12.5px;
  color: var(--av-ink-dim);
  text-align: center;
}

/* ── Click-nudge highlight: breathing halo + periodic light sweep. ─────── */
.av__pulse {
  position: relative;
  overflow: hidden;
  animation: av-pulse 2.6s ease-out 1.4s infinite;
}

.av__pulse::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 38%;
  background: linear-gradient(105deg, transparent, rgba(247, 243, 236, 0.32), transparent);
  transform: skewX(-18deg) translateX(-160%);
  animation: av-shine 2.6s ease-in-out 1.6s infinite;
  pointer-events: none;
}

@keyframes av-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(23, 19, 13, 0.35);
  }
  55%,
  100% {
    box-shadow: 0 0 0 9px transparent;
  }
}

@keyframes av-shine {
  0% {
    transform: skewX(-18deg) translateX(-160%);
  }
  42%,
  100% {
    transform: skewX(-18deg) translateX(440%);
  }
}

/* ── Entrance animation ────────────────────────────────────────────────── */
@media (prefers-reduced-motion: no-preference) {
  .av__kicker,
  .av__title,
  .av__lede,
  .av__stage,
  .av__cta-row,
  .av__signature {
    animation-name: av-rise;
    animation-duration: 0.55s;
    animation-timing-function: cubic-bezier(0.2, 0.7, 0.3, 1);
    animation-fill-mode: both;
  }
  .av__title {
    animation-delay: 0.05s;
  }
  .av__lede {
    animation-delay: 0.1s;
  }
  .av__stage {
    animation-delay: 0.16s;
  }
  .av__cta-row {
    animation-delay: 0.24s;
  }
  .av__signature {
    animation-delay: 0.3s;
  }
}

@keyframes av-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .av__pulse {
    animation: none;
  }
  .av__pulse::after {
    display: none;
  }
}
</style>
