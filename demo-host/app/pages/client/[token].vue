<template>
  <div class="cs" :style="accentStyle">
    <ClientSpaceAccessMessage
      v-if="state === 'loading' || state === 'expired' || !space"
      :state="state"
      :renew-state="renewState"
      @renew="renewLink"
    />

    <div v-else class="cs-shell">
      <ClientSpaceSidebar
        class="cs-shell__side"
        :business-name="space.business_name"
        :section="location.section"
        :pending-count="space.pending_count"
        :assistant-name="space.assistant_name"
        :portrait-url="portraitUrl"
        :portrait-fallback-url="portraitFallbackUrl"
        @navigate="openSection"
        @open-assistant="openSettingsScreen('assistant')"
        @open-help="openSettingsScreen('help')"
      />

      <div class="cs-shell__main" :class="{ 'cs-shell__main--detail': isDetailOpen }">
        <header v-if="!isDetailOpen" class="cs-bar cs-bar--top">
          <span class="cs-bar__title" :class="{ 'cs-bar__title--brand': location.section === 'home' }">{{
            topTitle
          }}</span>
          <button
            v-if="location.section === 'home'"
            type="button"
            class="cs-bar__btn"
            aria-label="Aide"
            @click="openSettingsScreen('help')"
          >
            <ClientSpaceIcon name="help-circle" />
          </button>
        </header>

        <p v-if="isExample && location.section === 'home'" class="cs-example" data-capture="example-banner">
          Exemple d’espace client, avec des données fictives : le vôtre arrive avec votre réceptionniste. Elle se
          présente toujours comme réceptionniste IA et ne donne jamais un prix à votre place : elle note, vous décidez.
          <NuxtLink v-if="demoSlug" :to="`/ia/${demoSlug}`" class="cs-example__link">Revenir à ma démo</NuxtLink>
        </p>

        <ClientSpaceHome
          v-if="location.section === 'home'"
          :space="space"
          :portrait-url="portraitUrl"
          :portrait-fallback-url="portraitFallbackUrl"
          @open-requests="openSection('requests')"
          @open-agenda="openSection('agenda')"
          @open-request="openRequest"
          @open-question="openQuestion"
          @open-settings-screen="openSettingsScreen"
        />

        <div v-else-if="location.section === 'requests'" class="cs-split">
          <div v-show="isWide || !isDetailOpen" class="cs-split__list">
            <ClientSpaceRequestList
              :requests="space.requests"
              :unanswered="space.unanswered"
              :assistant-name="space.assistant_name"
              :portrait-url="portraitUrl"
              :portrait-fallback-url="portraitFallbackUrl"
              :active-request-id="location.requestId"
              :active-question-index="location.questionIndex"
              @open="openRequest"
              @open-question="openQuestion"
            />
          </div>
          <div v-if="isWide || isDetailOpen" class="cs-split__detail">
            <ClientSpaceRequestDetail
              v-if="openedRequest"
              :request="openedRequest"
              :is-busy="busyRequestId === openedRequest.id"
              :error-message="requestError"
              :read-only="isExample"
              :show-back="!isWide"
              :gmail-drafts-url="space.mailbox?.drafts_url ?? null"
              @handled="markHandled"
              @dropped="markDropped"
              @outcome="setOutcome"
              @back="closeDetail"
            />
            <ClientSpaceQuestion
              v-else-if="openedQuestion"
              :entry="openedQuestion"
              :assistant-name="space.assistant_name"
              :portrait-url="portraitUrl"
              :portrait-fallback-url="portraitFallbackUrl"
              :is-busy="isQuestionBusy"
              :error-message="questionError"
              :read-only="isExample"
              :show-back="!isWide"
              @answer="answerOpenedQuestion"
              @dismiss="dismissOpenedQuestion"
              @back="closeDetail"
            />
            <div v-else-if="isDetailOpen" class="cs-split__placeholder">
              <ClientSpaceBackBar back-label="Demandes" @back="closeDetail" />
              <p class="cs-muted cs-split__hint">Cette demande n’est plus dans la liste.</p>
            </div>
            <p v-else class="cs-muted cs-split__hint">Ouvrez une demande pour la lire et rappeler.</p>
          </div>
        </div>

        <ClientSpaceAgenda
          v-else-if="location.section === 'agenda'"
          :calendar="space.calendar"
          :appointments="space.appointments"
          :requests="space.requests"
          :assistant-name="space.assistant_name"
          :is-busy="isCalendarBusy"
          :error-message="calendarError"
          :has-saved="hasSavedCalendar"
          :read-only="isExample"
          @connect="connectCalendar"
          @save="saveCalendar"
          @disconnect="disconnectCalendar"
          @open-request="openRequest"
        />

        <template v-else>
          <ClientSpaceSettingsMenu
            v-if="!location.settingsScreen"
            :space="space"
            @open="openSettingsScreen"
            @open-agenda="openSection('agenda')"
            @open-questions="openSection('requests')"
          />
          <div v-else class="cs-screen">
            <ClientSpaceBackBar back-label="Réglages" :title="settingsTitle" @back="closeDetail" />

            <ClientSpaceSettings
              v-if="location.settingsScreen === 'assistant' || location.settingsScreen === 'alerts'"
              :key="location.settingsScreen"
              :part="location.settingsScreen"
              :settings="space.settings"
              :language-options="space.language_options"
              :is-saving="isSavingSettings"
              :error-message="settingsError"
              :has-saved="hasSavedSettings"
              :test-sms-state="testSmsState"
              :test-sms-message="testSmsMessage"
              :read-only="isExample"
              @test-sms="sendTestSms"
              @save="saveSettings"
            />

            <ClientSpaceLimits
              v-else-if="location.settingsScreen === 'limits'"
              :limits="space.limits"
              :assistant-name="space.assistant_name"
              :is-saving="isSavingLimits"
              :error-message="limitsError"
              :has-saved="hasSavedLimits"
              :read-only="isExample"
              @save="saveLimits"
            />

            <ClientSpaceLearnedAnswers
              v-else-if="location.settingsScreen === 'learned'"
              :faq="space.faq"
              :assistant-name="space.assistant_name"
            />

            <ClientSpaceReport
              v-else-if="location.settingsScreen === 'report'"
              :report="space.report"
              :assistant-name="space.assistant_name"
            />

            <ClientSpaceSubscription
              v-else-if="location.settingsScreen === 'subscription'"
              :subscription="space.subscription"
              :is-opening-billing-portal="isOpeningBillingPortal"
              :billing-portal-error="billingPortalError"
              :read-only="isExample"
              @open-billing-portal="openBillingPortal"
            />

            <ClientSpaceGoogleProfile
              v-else-if="location.settingsScreen === 'google' && space.google_profile"
              :google-profile="space.google_profile"
              :assistant-name="space.assistant_name"
              :is-saving="isSavingGoogleProfile"
              :error-message="googleProfileError"
              :read-only="isExample"
              @linked="setGoogleProfileLinked"
            />

            <ClientSpaceInstallGuide
              v-else-if="location.settingsScreen === 'install'"
              :installed="space.installed"
              :embed-snippet="space.embed_snippet"
              :website-url="space.website_url"
              :assistant-name="space.assistant_name"
              :business-name="space.business_name"
            />

            <ClientSpaceMailbox
              v-else-if="location.settingsScreen === 'mailbox' && space.mailbox"
              :mailbox="space.mailbox"
              :assistant-name="space.assistant_name"
              :is-busy="isMailboxBusy"
              :error-message="mailboxError"
              :read-only="isExample"
              @connect="connectMailbox"
              @disconnect="disconnectMailbox"
            />

            <ClientSpaceHelp v-else :is-example="isExample" :link-expires-label="space.link_expires_label" />
          </div>
        </template>
      </div>

      <ClientSpaceTabBar
        v-if="!isDetailOpen"
        class="cs-shell__tabs"
        :section="location.section"
        :pending-count="space.pending_count"
        @navigate="openSection"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type {
  AiAssistantClientRequest,
  AiAssistantClientSpaceLoad,
  AiAssistantClientUnansweredEntry,
} from '~/types/AiAssistantClientSpace'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import type { ClientSpaceSection, ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'
import type { UseClientSpaceCalendarReturn } from '~/types/UseClientSpaceCalendar'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import type { UseClientSpaceMailboxReturn } from '~/types/UseClientSpaceMailbox'
import type { UseClientSpaceRequestsReturn } from '~/types/UseClientSpaceRequests'
import type { UseClientSpaceSettingsReturn } from '~/types/UseClientSpaceSettings'
import { useClientSpaceCalendar } from '~/composables/useClientSpaceCalendar'
import { useClientSpaceLink } from '~/composables/useClientSpaceLink'
import { useClientSpaceMailbox } from '~/composables/useClientSpaceMailbox'
import { useClientSpaceNavigation } from '~/composables/useClientSpaceNavigation'
import { useClientSpaceRequests } from '~/composables/useClientSpaceRequests'
import { useClientSpaceSettings } from '~/composables/useClientSpaceSettings'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantAvatarUtils } from '~/utils/AssistantAvatarUtils'

const route: ReturnType<typeof useRoute> = useRoute()
const link: UseClientSpaceLinkReturn = useClientSpaceLink()
const { token, state, space, renewState, fetchSpace, setLoadResult, renewLink }: UseClientSpaceLinkReturn = link

const { data: load }: Awaited<ReturnType<typeof useAsyncData<AiAssistantClientSpaceLoad | undefined>>> =
  await useAsyncData<AiAssistantClientSpaceLoad>(
    () => `client-space-${token.value}`,
    fetchSpace,
    // Loaded by the visitor's browser: the API rate-limits per visitor, never per demo-host server.
    { server: false },
  )

const {
  location,
  isDetailOpen,
  openSection,
  openRequest,
  openQuestion,
  openSettingsScreen,
  closeDetail,
}: ReturnType<typeof useClientSpaceNavigation> = useClientSpaceNavigation()

const {
  busyRequestId,
  requestError,
  isQuestionBusy,
  questionError,
  markHandled,
  markDropped,
  setOutcome,
  answerQuestion,
  dismissQuestion,
}: UseClientSpaceRequestsReturn = useClientSpaceRequests(link)

const {
  isSavingSettings,
  settingsError,
  hasSavedSettings,
  testSmsState,
  testSmsMessage,
  isSavingLimits,
  limitsError,
  hasSavedLimits,
  isSavingGoogleProfile,
  googleProfileError,
  isOpeningBillingPortal,
  billingPortalError,
  saveSettings,
  sendTestSms,
  saveLimits,
  setGoogleProfileLinked,
  openBillingPortal,
  clearScreenFeedback,
}: UseClientSpaceSettingsReturn = useClientSpaceSettings(link)

const {
  isCalendarBusy,
  calendarError,
  hasSavedCalendar,
  connectCalendar,
  saveCalendar,
  disconnectCalendar,
  clearCalendarFeedback,
}: UseClientSpaceCalendarReturn = useClientSpaceCalendar(link)

const {
  isMailboxBusy,
  mailboxError,
  connectMailbox,
  disconnectMailbox,
  clearMailboxFeedback,
}: UseClientSpaceMailboxReturn = useClientSpaceMailbox(link)

useHead({
  title: computed((): string => (space.value ? `Espace client · ${space.value.business_name}` : 'Espace client')),
  meta: [
    { name: 'robots', content: 'noindex, nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

const SETTINGS_TITLES: Record<ClientSpaceSettingsScreen, string> = {
  assistant: 'Votre réceptionniste',
  alerts: 'Vous prévenir',
  learned: 'Ce que vous lui avez appris',
  report: 'Rapport du mois',
  subscription: 'Abonnement',
  limits: 'Prix, délais, garanties',
  google: 'Votre fiche Google',
  install: 'Sur votre site',
  mailbox: 'Votre boîte mail',
  help: 'Aide',
}

/** From this width, the sidebar replaces the tab bar and a request opens beside the list. */
const WIDE_QUERY: string = '(min-width: 1024px)'

let wideQuery: MediaQueryList | null = null

const isWide: Ref<boolean> = ref(false)

/** The receptionist's portrait, as the widget shows it (the gender is unknown here: a casting name has its own). */
const portraitUrl: ComputedRef<string> = computed((): string =>
  AssistantAvatarUtils.portraitUrl(space.value?.assistant_name ?? '', null),
)

const portraitFallbackUrl: ComputedRef<string> = computed((): string =>
  AssistantAvatarUtils.dataUri(
    space.value?.assistant_name ?? '',
    null,
    AssistantAccentUtils.palette(space.value?.accent_color).tint,
  ),
)

/**
 * The business's colour in its shades, as the widget derives them, so any colour stays readable: the text shade
 * and the tint exist for the day and for the night, the stylesheet picks the pair the screen wants.
 */
const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => {
  const light: AssistantAccentPalette = AssistantAccentUtils.palette(space.value?.accent_color)
  const dark: AssistantAccentPalette = AssistantAccentUtils.darkPalette(space.value?.accent_color)
  return {
    '--a-accent': light.accent,
    '--cs-accent': light.accent,
    '--cs-accent-strong': light.strong,
    '--cs-accent-text-light': light.text,
    '--cs-accent-tint-light': light.tint,
    '--cs-accent-text-dark': dark.text,
    '--cs-accent-tint-dark': dark.tint,
  }
})

/** The example space a prospect reads from its demo page: fictional data, nothing to save. */
const isExample: ComputedRef<boolean> = computed((): boolean => space.value?.is_example === true)

/** The demo the prospect came from (« ?demo=<slug> »), to offer the way back; empty when unknown or malformed. */
const demoSlug: ComputedRef<string> = computed((): string => {
  const raw: string = String(route.query.demo ?? '')
  return /^[a-z0-9-]{1,80}$/.test(raw) ? raw : ''
})

/** The request open on top of the list, if it is still listed. */
const openedRequest: ComputedRef<AiAssistantClientRequest | null> = computed((): AiAssistantClientRequest | null => {
  const id: number | null = location.value.requestId
  if (id === null) return null
  return space.value?.requests.find((item: AiAssistantClientRequest): boolean => item.id === id) ?? null
})

/** The receptionist's question open on top of the list, if it is still unanswered. */
const openedQuestion: ComputedRef<AiAssistantClientUnansweredEntry | null> = computed(
  (): AiAssistantClientUnansweredEntry | null => {
    const index: number | null = location.value.questionIndex
    if (index === null) return null
    return space.value?.unanswered[index] ?? null
  },
)

/** The phone's top bar: the business on the home, the section elsewhere. */
const topTitle: ComputedRef<string> = computed((): string => {
  if (location.value.section === 'home') return space.value?.business_name ?? ''
  if (location.value.section === 'requests') return 'Demandes'
  if (location.value.section === 'agenda') return 'Agenda'
  return 'Réglages'
})

const settingsTitle: ComputedRef<string> = computed((): string =>
  location.value.settingsScreen ? SETTINGS_TITLES[location.value.settingsScreen] : '',
)

/**
 * Answer the question that is open, then go back to the list.
 * @param answer - The answer to give from now on.
 * @returns A promise resolved once the API answered.
 */
async function answerOpenedQuestion(answer: string): Promise<void> {
  const entry: AiAssistantClientUnansweredEntry | null = openedQuestion.value
  if (!entry) return
  if (await answerQuestion(entry.question, answer)) closeDetail()
}

/**
 * Drop the question that is open without answering it, then go back to the list.
 * @returns A promise resolved once the API answered.
 */
async function dismissOpenedQuestion(): Promise<void> {
  const index: number | null = location.value.questionIndex
  if (index === null) return
  if (await dismissQuestion(index)) closeDetail()
}

/** Follow the screen's width: the sidebar and the split view above 1024 px, the tab bar below. */
function onWideChange(): void {
  isWide.value = wideQuery?.matches === true
}

watch(
  load,
  (value: AiAssistantClientSpaceLoad | undefined): void => {
    if (value) setLoadResult(value)
  },
  { immediate: true },
)

watch(
  (): ClientSpaceSettingsScreen | null => location.value.settingsScreen,
  (): void => {
    clearScreenFeedback()
    clearMailboxFeedback()
  },
)

watch((): ClientSpaceSection => location.value.section, clearCalendarFeedback)

onMounted((): void => {
  wideQuery = window.matchMedia(WIDE_QUERY)
  onWideChange()
  wideQuery.addEventListener('change', onWideChange)
})

onBeforeUnmount((): void => {
  wideQuery?.removeEventListener('change', onWideChange)
})
</script>

<style src="~/assets/css/client-space.css"></style>
