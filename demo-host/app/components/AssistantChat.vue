<template>
  <div
    class="ai-widget"
    :class="{ 'ai-widget--inline': props.inline, 'ai-widget--embedded': isEmbedded }"
    :style="accentStyle"
  >
    <Transition name="ai-open" :css="shouldAnimateOpening" @after-enter="onAfterEnter" @after-leave="onAfterLeave">
      <AssistantChatLauncher
        v-if="!isOpen"
        ref="launcherComponent"
        :lang="lang"
        :assistant-name="props.config.assistant_name"
        :avatar-url="avatarUrl"
        :avatar-fallback-url="avatarFallbackUrl"
        :is-mobile-layout="isMobileLayout"
        @open="open"
      />

      <section
        v-else
        class="ai-panel"
        :class="{ 'ai-panel--mobile': isMobileLayout && !props.inline, 'ai-panel--inline': props.inline }"
        role="dialog"
        :aria-label="props.config.assistant_name"
        @keydown.esc="close"
      >
        <AssistantChatHeader
          ref="headerComponent"
          :assistant-name="props.config.assistant_name"
          :business-name="props.config.business_name"
          :role-label="roleLabel"
          :online-label="onlineLabel"
          :avatar-url="avatarUrl"
          :avatar-fallback-url="avatarFallbackUrl"
          :can-close="!props.inline"
          :lang="lang"
          :languages="offeredLanguages"
          @close="close"
          @change-lang="setLang"
        />

        <div ref="threadElement" class="ai-thread">
          <div class="ai-thread__log" role="log" aria-live="polite" aria-relevant="additions">
            <AssistantChatMessageBubble
              v-for="(message, index) in messages"
              :key="index"
              :message="message"
              :photo-preview-url="photoPreviews[index] ?? null"
              :avatar-url="closesAssistantRun(index) ? avatarUrl : null"
              :avatar-fallback-url="avatarFallbackUrl"
              :assistant-name="props.config.assistant_name"
            />
            <AssistantChatTypingIndicator v-if="isBusy" :lang="lang" />
          </div>

          <AssistantChatQuickReplies
            v-if="showChips"
            :lang="lang"
            :suggestions="suggestions"
            :can-send-photo="photosRemaining > 0"
            :can-play-example="props.inline && !hasPlayedExample"
            @photo="openPhotoPanel"
            @appointment="openSlotPanel"
            @suggest="sendText"
            @example="playScriptedExample"
          />
          <AssistantChatQuickReplies
            v-else-if="followUps.length > 0 || showActionChips"
            :lang="lang"
            :suggestions="followUps"
            :can-send-photo="showActionChips && photosRemaining > 0"
            :can-book-appointment="showActionChips && !leadSent"
            @photo="openPhotoPanel"
            @appointment="openSlotPanel"
            @suggest="sendText"
          />

          <AssistantChatPhotoCard
            v-if="isPhotoPanelOpen"
            :lang="lang"
            :is-busy="isBusy"
            @pick="sendPhoto"
            @cancel="closePhotoPanel"
          />

          <AssistantChatSlotsCard
            v-if="isSlotPanelOpen"
            ref="slotsCard"
            :lang="lang"
            :booking-mode="bookingMode"
            :slots-state="slotsState"
            :days="slotDays"
            :times="slotTimes"
            :has-more-times="hasMoreTimes"
            :has-previous-page="hasPreviousSlotsPage"
            :kinds="appointmentKinds"
            :chosen-slots="chosenSlots"
            :chosen-time="chosenTime"
            :chosen-kind="chosenKind"
            :can-continue="canContinueBooking"
            @toggle-slot="toggleSlot"
            @choose-time="chooseTime"
            @choose-kind="chooseKind"
            @first-page="loadFirstSlotsPage"
            @more="showMoreTimes"
            @confirm="confirmSlots"
            @cancel="closeSlotPanel"
          />

          <AssistantChatContactForm
            v-if="showLeadForm && !leadSent"
            ref="contactForm"
            :lang="lang"
            :picked-summary="pickedSummary"
            :initial-need="leadNeedPrefill"
            :is-submitting="isSubmittingLead"
            @submit="submitLead"
            @cancel="cancelLeadForm"
          />
        </div>

        <AssistantChatCallbackBar v-if="showCallbackBar" :lang="lang" @open="openLeadForm" />

        <AssistantChatComposer
          v-model="draft"
          :lang="lang"
          :is-busy="isBusy || isStreaming"
          :can-send-photo="photosRemaining > 0"
          :can-book="!leadSent"
          @send="sendDraft"
          @photo="openPhotoPanel"
          @appointment="openSlotPanel"
        />
      </section>
    </Transition>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantChatEmits, AssistantChatProps, AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantDemoScriptStep, AssistantHostPage } from '~/types/AssistantDemoScript'
import type { UseAssistantConversationReturn } from '~/types/UseAssistantConversation'
import type { UseAssistantWidgetFrameReturn } from '~/types/UseAssistantWidgetFrame'
import AssistantChatContactForm from '~/components/AssistantChatContactForm.vue'
import AssistantChatHeader from '~/components/AssistantChatHeader.vue'
import AssistantChatLauncher from '~/components/AssistantChatLauncher.vue'
import AssistantChatSlotsCard from '~/components/AssistantChatSlotsCard.vue'
import { useAssistantConversation } from '~/composables/useAssistantConversation'
import { useAssistantWidgetFrame } from '~/composables/useAssistantWidgetFrame'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { ONLINE_LABELS, ROLE_LABELS } from '~/constants/AssistantWidgetLabels'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantAvatarUtils } from '~/utils/AssistantAvatarUtils'
import { AssistantDemoScenarioUtils } from '~/utils/AssistantDemoScenarioUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'

const props: AssistantChatProps = defineProps({
  config: {
    type: Object as PropType<AiAssistantConfig>,
    required: true,
  },
  inline: {
    type: Boolean,
    default: false,
  },
  hostPage: {
    type: Object as PropType<AssistantHostPage | null>,
    default: null,
  },
})

const emit: EmitFn<AssistantChatEmits> = defineEmits<AssistantChatEmits>()

const {
  messages,
  lang,
  offeredLanguages,
  suggestions,
  draft,
  isBusy,
  isStreaming,
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
  followUps,
  showActionChips,
  showCallbackBar,
  lastLeadSummary,
  hasPlayedExample,
  restore,
  restoreFromHost,
  greet,
  playExample,
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
}: UseAssistantConversationReturn = useAssistantConversation(props.config, props.inline, props.hostPage)

const isOpen: Ref<boolean> = ref(props.inline)
/** True while the panel plays its closing sheet: the loader keeps the frame large until it is gone. */
const isPanelLeaving: Ref<boolean> = ref(false)
/** False for one opening only: the loader's placeholder sheet already travelled, the panel takes its place at once. */
const shouldAnimateOpening: Ref<boolean> = ref(true)
/** What the loader must frame: the panel while it is open or still closing, the launcher otherwise. */
const isFrameOpen: ComputedRef<boolean> = computed((): boolean => isOpen.value || isPanelLeaving.value)
const launcherComponent: Ref<InstanceType<typeof AssistantChatLauncher> | null> = ref(null)
const headerComponent: Ref<InstanceType<typeof AssistantChatHeader> | null> = ref(null)
const slotsCard: Ref<InstanceType<typeof AssistantChatSlotsCard> | null> = ref(null)
const contactForm: Ref<InstanceType<typeof AssistantChatContactForm> | null> = ref(null)
const threadElement: Ref<HTMLElement | null> = ref(null)

const launcherElement: ComputedRef<HTMLElement | null> = computed(
  (): HTMLElement | null => launcherComponent.value?.rootElement ?? null,
)

const { isEmbedded, isMobileLayout, hostState }: UseAssistantWidgetFrameReturn = useAssistantWidgetFrame({
  inline: props.inline,
  isOpen: isFrameOpen,
  launcherElement,
  onOpenRequest: open,
})

const palette: ComputedRef<AssistantAccentPalette> = computed((): AssistantAccentPalette =>
  AssistantAccentUtils.palette(props.config.accent_color),
)
const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--ai-accent': palette.value.accent,
  '--ai-accent-strong': palette.value.strong,
  '--ai-accent-text': palette.value.text,
  '--ai-accent-tint': palette.value.tint,
}))
const avatarUrl: ComputedRef<string> = computed((): string =>
  AssistantAvatarUtils.portraitUrl(props.config.assistant_name, props.config.assistant_gender ?? null),
)
const avatarFallbackUrl: ComputedRef<string> = computed((): string =>
  AssistantAvatarUtils.dataUri(props.config.assistant_name, props.config.assistant_gender ?? null, palette.value.tint),
)
const roleLabel: ComputedRef<string> = computed(
  (): string => ROLE_LABELS[lang.value][props.config.assistant_gender ?? 'feminine'],
)
const onlineLabel: ComputedRef<string> = computed((): string => ONLINE_LABELS[lang.value])

/**
 * Whether the message ends a run of assistant replies: the portrait sits beside that one only.
 * @param index - The message's position in the thread.
 * @returns True for the last assistant bubble before a visitor message or the end of the thread.
 */
function closesAssistantRun(index: number): boolean {
  if (messages.value[index]?.role !== 'assistant') return false
  return messages.value[index + 1]?.role !== 'assistant'
}

/**
 * Open the panel, greet the visitor once, and move the keyboard focus inside.
 * @param instant - Show the panel without its opening sheet (the loader's placeholder already played it).
 */
function open(instant: boolean = false): void {
  if (instant) shouldAnimateOpening.value = false
  isOpen.value = true
  if (messages.value.length === 0) {
    if (!props.inline) captureDemoEvent('assistant_opened')
    greet()
  }
  if (!props.inline) nextTick((): void => headerComponent.value?.focusClose())
}

/** Play the demo page's scripted conversation for this trade, in the widget's language. */
function playScriptedExample(): void {
  const steps: AssistantDemoScriptStep[] = AssistantDemoScenarioUtils.script(
    lang.value,
    props.config.trade_label ?? null,
    BusinessNameUtils.short(props.config.business_name),
  )
  playExample(steps)
}

/** Close the panel (it slides back to the launcher) and give the keyboard focus back to the launcher. */
function close(): void {
  if (props.inline) return
  isPanelLeaving.value = true
  isOpen.value = false
  nextTick((): void => launcherComponent.value?.focus())
}

/** The panel is in place: the next opening animates again. */
function onAfterEnter(): void {
  shouldAnimateOpening.value = true
}

/**
 * The closing sheet is gone: the loader may now shrink the frame to the launcher.
 * @param element - The element that just left (the panel, or the launcher when the panel opened).
 */
function onAfterLeave(element: Element): void {
  if (element.classList.contains('ai-panel')) isPanelLeaving.value = false
}

/**
 * Scroll the thread to its latest entry once the DOM has updated.
 * @returns A promise resolved once scrolled.
 */
async function scrollToLatest(): Promise<void> {
  await nextTick()
  if (threadElement.value) threadElement.value.scrollTop = threadElement.value.scrollHeight
}

watch(
  [
    (): number => messages.value.length,
    (): string => messages.value[messages.value.length - 1]?.content ?? '',
    isBusy,
    // The follow-up chips appear once the reply has fully streamed: the thread scrolls to show them.
    isStreaming,
    isPhotoPanelOpen,
    isSlotPanelOpen,
    showLeadForm,
    slotsState,
  ],
  (): void => {
    scrollToLatest()
  },
)

watch(isSlotPanelOpen, async (isShown: boolean): Promise<void> => {
  if (!isShown) return
  // The chip that opened it disappears: keyboard focus moves into the card.
  await nextTick()
  slotsCard.value?.focus()
})

watch(showLeadForm, async (isShown: boolean): Promise<void> => {
  if (!isShown) return
  await nextTick()
  contactForm.value?.focusName()
})

watch(lastLeadSummary, (summary: AssistantLeadSummary | null): void => {
  if (summary) emit('lead-sent', summary)
})

watch(hasPlayedExample, (hasPlayed: boolean): void => {
  if (hasPlayed) emit('example-played')
})

watch(hostState, (raw: string | null | undefined): void => {
  if (raw !== undefined) restoreFromHost(raw)
})

onMounted((): void => {
  restore()
  // Laid out in place: the conversation is the page's content, open from the start.
  if (props.inline) open()
})

onBeforeUnmount((): void => {
  releasePhotoPreviews()
})
</script>

<style scoped>
.ai-widget {
  --ai-paper: #f4f0e8;
  --ai-paper-2: #faf8f3;
  --ai-card: #ffffff;
  --ai-ink: #17130d;
  --ai-ink-dim: #6d665b;
  --ai-line: rgba(23, 19, 13, 0.12);
  --ai-line-soft: rgba(23, 19, 13, 0.07);
  --ai-on-strong: #ffffff;
  --ai-online: #2f9e5b;
  --ai-font-d: 'Fraunces', Georgia, serif;
  --ai-font-b: 'Inter', system-ui, sans-serif;
  font-family: var(--ai-font-b);
  color: var(--ai-ink);
}
.ai-widget--inline {
  height: 100%;
}
/* On a client's site the loader draws the launcher itself: the widget's own only sizes the frame, unseen. */
.ai-widget--embedded :deep(.ai-launcher) {
  visibility: hidden;
  pointer-events: none;
  transition: none;
}
.ai-panel {
  position: fixed;
  right: max(22px, env(safe-area-inset-right, 0px));
  bottom: max(22px, env(safe-area-inset-bottom, 0px));
  z-index: 60;
  width: 392px;
  max-width: calc(100vw - 28px);
  height: min(628px, calc(100vh - 44px));
  background: var(--ai-card);
  border: 1px solid var(--ai-line);
  border-radius: 22px;
  box-shadow: 0 30px 70px -30px rgba(23, 19, 13, 0.45);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ai-panel--inline {
  position: relative;
  inset: auto;
  width: 100%;
  max-width: none;
  height: 100%;
  border: 0;
  border-radius: 0;
  box-shadow: none;
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

/* ── Opening and closing: a fade that rises (Léo's pick, 26/09), quick and discreet, same on a phone ──── */
.ai-open-enter-active.ai-panel {
  will-change: transform, opacity;
  transition:
    opacity 0.26s cubic-bezier(0.2, 0.7, 0.2, 1),
    transform 0.3s cubic-bezier(0.2, 0.7, 0.2, 1);
}
.ai-open-leave-active.ai-panel {
  will-change: transform, opacity;
  transition:
    opacity 0.18s ease-in,
    transform 0.18s ease-in;
}
.ai-open-enter-from.ai-panel,
.ai-open-leave-to.ai-panel {
  opacity: 0;
  transform: translate3d(0, 14px, 0);
}
/* The launcher steps aside quickly and pops back a beat after the sheet has gone. */
.ai-open-enter-active.ai-launcher {
  transition:
    opacity 0.3s cubic-bezier(0.32, 0.72, 0, 1) 0.08s,
    transform 0.3s cubic-bezier(0.32, 0.72, 0, 1) 0.08s;
}
.ai-open-leave-active.ai-launcher {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}
.ai-open-enter-from.ai-launcher,
.ai-open-leave-to.ai-launcher {
  opacity: 0;
  transform: scale(0.7);
}
@media (prefers-reduced-motion: reduce) {
  .ai-open-enter-active,
  .ai-open-leave-active {
    transition-duration: 0.15s;
    transition-delay: 0s;
  }
  .ai-open-enter-from,
  .ai-open-leave-to {
    transform: none;
  }
}
/* The widget's own focus ring, never the browser's blue one. */
.ai-widget :deep(:focus:not(:focus-visible)) {
  outline: none;
}
.ai-widget :deep(:focus-visible) {
  outline: 2px solid var(--ai-accent-strong);
  outline-offset: 2px;
}
.ai-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--ai-paper-2);
  scrollbar-width: thin;
}
.ai-thread__log {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
