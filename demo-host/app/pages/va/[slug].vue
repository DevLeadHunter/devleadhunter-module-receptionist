<template>
  <div v-if="pending" class="av av--message">Chargement…</div>
  <div v-else-if="!assistant || !assistant.video_available" class="av av--message av--error">
    Vidéo introuvable ou pas encore prête.
  </div>
  <main v-else class="av" :style="accentStyle">
    <div class="av__content">
      <p class="av__kicker">Assistant en ligne</p>
      <h1 class="av__title">
        L'assistant de <em>{{ assistant.business_name }}</em> vous répond<span class="av__dot">.</span>
      </h1>
      <p class="av__lede">
        <template v-if="videoDurationSeconds"
          ><strong>{{ videoDurationSeconds }} secondes</strong> pour le voir en action,</template
        >
        <template v-else>Regardez-le en action,</template>
        puis essayez-le vous-même.
      </p>

      <div class="av__frame">
        <video
          ref="playerRef"
          class="av__player"
          :src="assistant.video_url ?? ''"
          :poster="assistant.video_thumbnail_url ?? ''"
          playsinline
          preload="metadata"
          @loadedmetadata="readDuration"
          @play="onPlay"
        />
        <button
          v-if="!hasStarted"
          type="button"
          class="av__overlay"
          aria-label="Lancer la vidéo"
          @click="startPlayback"
        >
          <span class="av__play">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <polygon points="8 5 19 12 8 19" />
            </svg>
          </span>
          <span class="av__play-label">Lancer la démo{{ durationSuffix }}</span>
        </button>
      </div>

      <a class="av__cta" :href="demoHref" @click="trackCta">Essayer l'assistant →</a>
    </div>
  </main>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onMounted, ref } from 'vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import { captureDemoEvent, useDemoTracking } from '~/composables/useDemoTracking'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'

const FALLBACK_ACCENT: string = '#a9793f'

const route: ReturnType<typeof useRoute> = useRoute()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
const slug: ComputedRef<string> = computed((): string => String(route.params.slug ?? ''))

const playerRef: Ref<HTMLVideoElement | null> = ref(null)
const videoDurationSeconds: Ref<number | null> = ref(null)
const hasStarted: Ref<boolean> = ref(false)

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

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--av-accent': assistant.value?.accent_color || FALLBACK_ACCENT,
}))

const durationSuffix: ComputedRef<string> = computed((): string =>
  videoDurationSeconds.value ? ` — ${videoDurationSeconds.value} s` : '',
)

/** Link to try the assistant, tagged internal-free so the prospect's visit is tracked. */
const demoHref: ComputedRef<string> = computed((): string => `/a/${slug.value}`)

/** Read the video duration once its metadata loads. */
function readDuration(): void {
  const seconds: number | undefined = playerRef.value?.duration
  if (seconds && Number.isFinite(seconds)) videoDurationSeconds.value = Math.round(seconds)
}

/** Start playback from the poster overlay. */
function startPlayback(): void {
  hasStarted.value = true
  void playerRef.value?.play()
}

/** Track the first play (PostHog). */
function onPlay(): void {
  captureDemoEvent('assistant_video_play')
}

/** Track a click on the « essayer l'assistant » CTA (PostHog). */
function trackCta(): void {
  captureDemoEvent('assistant_video_cta_click')
}

const { init: initTracking }: ReturnType<typeof useDemoTracking> = useDemoTracking()

onMounted((): void => {
  const current: AiAssistantConfig | null | undefined = assistant.value
  if (!current) return
  void initTracking(current.slug, current.status, null, DemoBeaconUtils.channelFromQuery(route.query.src), 'assistant')
})

useHead({
  title: computed((): string => `${assistant.value?.business_name ?? 'Assistant'} — vidéo`),
  link: [
    {
      rel: 'stylesheet',
      href: 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600&display=swap',
    },
  ],
})
</script>

<style scoped>
.av {
  min-height: 100dvh;
  background: #f7f3ec;
  color: #17130d;
  font-family: 'Inter', system-ui, sans-serif;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}
.av--message {
  color: #6d665b;
  font-size: 0.95rem;
}
.av--error {
  color: #9f3a2f;
}
.av__content {
  width: 100%;
  max-width: 760px;
}
.av__kicker {
  margin: 0;
  font-size: 0.72rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--av-accent);
}
.av__title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(2rem, 5vw, 3.1rem);
  line-height: 1.06;
  margin: 14px 0 12px;
  text-wrap: balance;
}
.av__title em {
  font-style: italic;
}
.av__dot {
  color: var(--av-accent);
}
.av__lede {
  margin: 0 0 26px;
  font-size: 1.02rem;
  color: #6d665b;
  max-width: 46ch;
}
.av__frame {
  position: relative;
  border-radius: 16px;
  overflow: hidden;
  background: #000;
  box-shadow: 0 18px 50px rgba(23, 19, 13, 0.2);
  aspect-ratio: 16 / 9;
}
.av__player {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.av__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  border: none;
  cursor: pointer;
  background: rgba(23, 19, 13, 0.28);
  color: #fff;
}
.av__play {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--av-accent);
  color: #fff;
  padding-left: 4px;
}
.av__play-label {
  font-size: 0.9rem;
  font-weight: 600;
}
.av__cta {
  display: inline-block;
  margin-top: 26px;
  padding: 13px 26px;
  border-radius: 999px;
  background: var(--av-accent);
  color: #fff;
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
}
</style>
