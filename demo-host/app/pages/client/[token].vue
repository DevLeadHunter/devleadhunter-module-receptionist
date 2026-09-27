<template>
  <div class="cs" :style="accentStyle">
    <main v-if="state === 'loading'" class="cs-message">
      <p class="cs-muted">Chargement…</p>
    </main>

    <main v-else-if="state === 'expired'" class="cs-message">
      <h1 class="cs-message__title">Ce lien a expiré</h1>
      <p class="cs-muted">Pour protéger vos demandes, un lien ne dure que 30 jours.</p>
      <button v-if="renewState === 'idle'" type="button" class="cs-btn cs-btn--primary" @click="renewLink">
        Recevoir un nouveau lien par email
      </button>
      <p v-else-if="renewState === 'sending'" class="cs-muted">Envoi…</p>
      <p v-else-if="renewState === 'sent'" class="cs-notice">
        C’est envoyé : ouvrez le nouveau lien depuis votre boîte mail.
      </p>
      <p v-else class="cs-notice cs-notice--error">
        Envoi impossible pour le moment : répondez à l’un de nos emails, on vous renvoie un lien.
      </p>
    </main>

    <main v-else-if="!space" class="cs-message">
      <h1 class="cs-message__title">{{ state === 'unavailable' ? 'Espace indisponible' : 'Lien invalide' }}</h1>
      <p class="cs-muted">
        {{
          state === 'unavailable'
            ? 'Réessayez dans quelques minutes.'
            : 'Ce lien n’ouvre aucun espace. Utilisez le dernier lien reçu par email ou par SMS.'
        }}
      </p>
    </main>

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

        <p v-if="isExample && location.section === 'home'" class="cs-example">
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
              :error-message="actionError"
              :read-only="isExample"
              :show-back="!isWide"
              @handled="markHandled"
              @dropped="markDropped"
              @back="closeDetail"
            />
            <ClientSpaceQuestion
              v-else-if="openedQuestion"
              :entry="openedQuestion"
              :assistant-name="space.assistant_name"
              :portrait-url="portraitUrl"
              :portrait-fallback-url="portraitFallbackUrl"
              :is-busy="isSavingFaq"
              :error-message="faqError"
              :read-only="isExample"
              :show-back="!isWide"
              @answer="answerOpenedQuestion"
              @dismiss="dismissOpenedQuestion"
              @back="closeDetail"
            />
            <div v-else-if="isDetailOpen" class="cs-split__placeholder">
              <header class="cs-bar">
                <button type="button" class="cs-bar__back" @click="closeDetail">
                  <ClientSpaceIcon name="chevron-left" />Demandes
                </button>
              </header>
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
            <header class="cs-bar">
              <button type="button" class="cs-bar__back" @click="closeDetail">
                <ClientSpaceIcon name="chevron-left" />Réglages
              </button>
              <span class="cs-bar__title cs-bar__title--center">{{ settingsTitle }}</span>
            </header>

            <ClientSpaceSettings
              v-if="location.settingsScreen === 'assistant' || location.settingsScreen === 'alerts'"
              :key="location.settingsScreen"
              :part="location.settingsScreen"
              :settings="space.settings"
              :language-options="space.language_options"
              :is-saving="isSavingSettings"
              :error-message="settingsError"
              :has-saved="hasSavedSettings"
              :read-only="isExample"
              @save="saveSettings"
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

            <div v-else-if="location.settingsScreen === 'subscription'" class="cs-screen__body">
              <p class="cs-sec">Votre abonnement</p>
              <div class="cs-block">
                <p v-if="!space.subscription" class="cs-text cs-text--dim">Aucun abonnement enregistré.</p>
                <template v-else>
                  <p class="cs-text">
                    <b>{{ space.subscription.price_label }}</b> · {{ subscriptionLabel }}
                    <template v-if="periodLine"><br />{{ periodLine }}</template>
                  </p>
                  <div v-if="space.subscription.can_manage && !isExample" class="cs-screen__actions">
                    <button type="button" class="cs-btn" :disabled="isOpeningPortal" @click="openPortal">
                      <ClientSpaceIcon name="external-link" />
                      {{ isOpeningPortal ? 'Ouverture…' : 'Factures, carte bancaire, résiliation' }}
                    </button>
                    <p v-if="portalError" class="cs-notice cs-notice--error">{{ portalError }}</p>
                  </div>
                </template>
              </div>
              <p class="cs-sec">Bon à savoir</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">
                  Sans engagement : la résiliation prend effet à la fin du mois en cours. Le premier mois est satisfait
                  ou remboursé.
                </p>
              </div>
            </div>

            <div v-else class="cs-screen__body">
              <p class="cs-sec">Une question ?</p>
              <div class="cs-block">
                <p class="cs-text">
                  Répondez à l’un des emails que vous avez reçus de nous, ou écrivez-nous depuis l’adresse de votre
                  entreprise : on vous répond en personne, généralement dans la journée.
                </p>
              </div>
              <p class="cs-sec">Votre lien</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">
                  <template v-if="isExample">Cet exemple n’a pas de lien personnel.</template>
                  <template v-else>
                    Ce lien personnel est valable jusqu’au {{ space.link_expires_label }}. Il donne accès à vos demandes
                    : ne le transférez pas. Vous en recevez un nouveau par email quand il expire.
                  </template>
                </p>
              </div>
            </div>
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
  AiAssistantClientCalendar,
  AiAssistantClientCalendarConnect,
  AiAssistantClientCalendarUpdate,
  AiAssistantClientFaqResponse,
  AiAssistantClientPortal,
  AiAssistantClientRenew,
  AiAssistantClientRenewState,
  AiAssistantClientRequest,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
  AiAssistantClientSpace,
  AiAssistantClientSpaceLoad,
  AiAssistantClientSpaceState,
  AiAssistantClientSubscription,
  AiAssistantClientSubscriptionStatus,
  AiAssistantClientUnansweredEntry,
} from '~/types/AiAssistantClientSpace'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import type { ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'
import { useClientSpaceNavigation } from '~/composables/useClientSpaceNavigation'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantAvatarUtils } from '~/utils/AssistantAvatarUtils'

const SUBSCRIPTION_LABELS: Record<AiAssistantClientSubscriptionStatus, string> = {
  incomplete: 'en attente',
  active: 'actif',
  past_due: 'paiement en attente',
  canceled: 'résilié',
}

const SETTINGS_TITLES: Record<ClientSpaceSettingsScreen, string> = {
  assistant: 'Votre réceptionniste',
  alerts: 'Vous prévenir',
  learned: 'Ce que vous lui avez appris',
  report: 'Rapport du mois',
  subscription: 'Abonnement',
  help: 'Aide',
}

/** From this width, the sidebar replaces the tab bar and a request opens beside the list. */
const WIDE_QUERY: string = '(min-width: 1024px)'

const route: ReturnType<typeof useRoute> = useRoute()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
const token: ComputedRef<string> = computed((): string => String(route.params.token ?? ''))
const endpoint: ComputedRef<string> = computed(
  (): string => `${config.public.apiBase}/api/v1/ai-assistants/client/${encodeURIComponent(token.value)}`,
)

const { data: load }: Awaited<ReturnType<typeof useAsyncData<AiAssistantClientSpaceLoad | undefined>>> =
  await useAsyncData<AiAssistantClientSpaceLoad>(
    () => `client-space-${token.value}`,
    async (): Promise<AiAssistantClientSpaceLoad> => {
      try {
        return { state: 'ready', space: await $fetch<AiAssistantClientSpace>(endpoint.value) }
      } catch (error: unknown) {
        const status: number | undefined = ApiRefusalUtils.status(error)
        if (status === 401) return { state: 'expired', space: null }
        if (status === 404) return { state: 'invalid', space: null }
        return { state: 'unavailable', space: null }
      }
    },
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

const state: Ref<AiAssistantClientSpaceState> = ref('loading')
const space: Ref<AiAssistantClientSpace | null> = ref(null)
const isWide: Ref<boolean> = ref(false)
const busyRequestId: Ref<number | null> = ref(null)
const actionError: Ref<string | null> = ref(null)
const isSavingSettings: Ref<boolean> = ref(false)
const settingsError: Ref<string | null> = ref(null)
const isSavingFaq: Ref<boolean> = ref(false)
const faqError: Ref<string | null> = ref(null)
const hasSavedSettings: Ref<boolean> = ref(false)
const isOpeningPortal: Ref<boolean> = ref(false)
const portalError: Ref<string | null> = ref(null)
const renewState: Ref<AiAssistantClientRenewState> = ref('idle')
const isCalendarBusy: Ref<boolean> = ref(false)
const calendarError: Ref<string | null> = ref(null)
const hasSavedCalendar: Ref<boolean> = ref(false)
// Google opened in another tab: the space reloads when the client comes back to this one.
const isAwaitingCalendar: Ref<boolean> = ref(false)
let wideQuery: MediaQueryList | null = null

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

/** The business's colour in its four shades, as the widget derives them, so any colour stays readable. */
const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => {
  const palette: AssistantAccentPalette = AssistantAccentUtils.palette(space.value?.accent_color)
  return {
    '--a-accent': palette.accent,
    '--cs-accent': palette.accent,
    '--cs-accent-strong': palette.strong,
    '--cs-accent-text': palette.text,
    '--cs-accent-tint': palette.tint,
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

const subscriptionLabel: ComputedRef<string> = computed((): string =>
  space.value?.subscription ? SUBSCRIPTION_LABELS[space.value.subscription.status] : '',
)

const periodLine: ComputedRef<string> = computed((): string => {
  const subscription: AiAssistantClientSubscription | null = space.value?.subscription ?? null
  if (!subscription?.period_end_label) return ''
  if (subscription.status === 'canceled' || subscription.cancel_scheduled) {
    return `Résiliation prévue, accès jusqu’au ${subscription.period_end_label}.`
  }
  if (subscription.status === 'past_due') return `Échéance du ${subscription.period_end_label}.`
  return `Prochain renouvellement le ${subscription.period_end_label}.`
})

/**
 * Switch to the « lien expiré » screen when the link lapsed during the visit.
 * @param error What `$fetch` threw.
 * @returns True when the link had expired.
 */
function showExpiredOnUnauthorized(error: unknown): boolean {
  if (ApiRefusalUtils.status(error) !== 401) return false
  state.value = 'expired'
  space.value = null
  return true
}

/**
 * The message a failed call shows, unless the link lapsed: the page then switches to the « lien expiré » screen.
 * @param error What `$fetch` threw.
 * @param fallback The message when the API gave no readable reason.
 * @returns Null on a 401, else the API's detail or the fallback.
 */
function failureMessage(error: unknown, fallback: string): string | null {
  if (showExpiredOnUnauthorized(error)) return null
  return ApiRefusalUtils.detail(error) ?? fallback
}

/**
 * Replace a request in the list with what the API returned, and keep the pending count right.
 * @param updated The request as the API returned it.
 */
function replaceRequest(updated: AiAssistantClientRequest): void {
  const current: AiAssistantClientSpace | null = space.value
  if (!current) return
  const wasPending: boolean = current.requests.some(
    (item: AiAssistantClientRequest): boolean => item.id === updated.id && item.status === 'new',
  )
  current.requests = current.requests.map((item: AiAssistantClientRequest): AiAssistantClientRequest =>
    item.id === updated.id ? updated : item,
  )
  if (wasPending && updated.status !== 'new') current.pending_count = Math.max(0, current.pending_count - 1)
}

/**
 * Change a request's status through the API and reflect it in the list.
 * @param requestId The request.
 * @param action « handled » or « dropped ».
 * @returns A promise resolved once the API answered.
 */
async function changeRequest(requestId: number, action: 'handled' | 'dropped'): Promise<void> {
  if (!space.value || busyRequestId.value !== null) return
  busyRequestId.value = requestId
  actionError.value = null
  try {
    const updated: AiAssistantClientRequest = await $fetch<AiAssistantClientRequest>(
      `${endpoint.value}/requests/${requestId}/${action}`,
      { method: 'POST' },
    )
    replaceRequest(updated)
  } catch (error: unknown) {
    actionError.value = failureMessage(error, 'La demande n’a pas pu être mise à jour, réessayez dans un instant.')
  } finally {
    busyRequestId.value = null
  }
}

/**
 * Mark a request called back.
 * @param requestId The request.
 * @returns A promise resolved once the API answered.
 */
async function markHandled(requestId: number): Promise<void> {
  await changeRequest(requestId, 'handled')
}

/**
 * Set a request aside: a test, spam, a duplicate.
 * @param requestId The request.
 * @returns A promise resolved once the API answered.
 */
async function markDropped(requestId: number): Promise<void> {
  await changeRequest(requestId, 'dropped')
}

/**
 * Record the business's answer to a question the receptionist could not answer; both lists come back updated.
 * @param question The question as it was asked.
 * @param answer The answer to give from now on.
 * @returns A promise resolved once the API answered.
 */
async function answerQuestion(question: string, answer: string): Promise<boolean> {
  const current: AiAssistantClientSpace | null = space.value
  if (!current || isSavingFaq.value) return false
  isSavingFaq.value = true
  faqError.value = null
  try {
    const lists: AiAssistantClientFaqResponse = await $fetch<AiAssistantClientFaqResponse>(`${endpoint.value}/faq`, {
      method: 'POST',
      body: { question, answer },
    })
    current.faq = lists.faq
    current.unanswered = lists.unanswered
    return true
  } catch (error: unknown) {
    if (!showExpiredOnUnauthorized(error)) {
      faqError.value = 'La réponse n’a pas pu être enregistrée, réessayez dans un instant.'
    }
    return false
  } finally {
    isSavingFaq.value = false
  }
}

/**
 * Answer the question that is open, then go back to the list.
 * @param answer The answer to give from now on.
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
  const current: AiAssistantClientSpace | null = space.value
  const index: number | null = location.value.questionIndex
  if (!current || index === null || isSavingFaq.value) return
  isSavingFaq.value = true
  faqError.value = null
  try {
    await $fetch(`${endpoint.value}/unanswered/${index}`, { method: 'DELETE' })
    current.unanswered = current.unanswered.filter((_: unknown, position: number): boolean => position !== index)
    closeDetail()
  } catch (error: unknown) {
    if (!showExpiredOnUnauthorized(error)) {
      faqError.value = 'La question n’a pas pu être retirée, réessayez dans un instant.'
    }
  } finally {
    isSavingFaq.value = false
  }
}

/**
 * Save the settings the client changed.
 * @param update The changed fields only.
 * @returns A promise resolved once the API answered.
 */
async function saveSettings(update: AiAssistantClientSettingsUpdate): Promise<void> {
  const current: AiAssistantClientSpace | null = space.value
  if (!current || isSavingSettings.value) return
  isSavingSettings.value = true
  settingsError.value = null
  hasSavedSettings.value = false
  try {
    current.settings = await $fetch<AiAssistantClientSettings>(`${endpoint.value}/settings`, {
      method: 'PATCH',
      body: update,
    })
    if (update.assistant_name) current.assistant_name = current.settings.assistant_name
    hasSavedSettings.value = true
  } catch (error: unknown) {
    settingsError.value = failureMessage(error, 'Enregistrement impossible, réessayez dans un instant.')
  } finally {
    isSavingSettings.value = false
  }
}

/**
 * Open the Stripe billing portal of the client's subscription.
 * @returns A promise resolved once redirected, or once the failure is shown.
 */
async function openPortal(): Promise<void> {
  if (isOpeningPortal.value) return
  isOpeningPortal.value = true
  portalError.value = null
  try {
    const portal: AiAssistantClientPortal = await $fetch<AiAssistantClientPortal>(`${endpoint.value}/billing-portal`, {
      method: 'POST',
    })
    window.location.assign(portal.url)
  } catch (error: unknown) {
    portalError.value = failureMessage(error, 'Ouverture impossible, réessayez dans un instant.')
    isOpeningPortal.value = false
  }
}

/**
 * Ask for a fresh link: it goes to the business's email address, never shown here.
 * @returns A promise resolved once the API answered.
 */
async function renewLink(): Promise<void> {
  renewState.value = 'sending'
  try {
    const answer: AiAssistantClientRenew = await $fetch<AiAssistantClientRenew>(`${endpoint.value}/renew`, {
      method: 'POST',
    })
    renewState.value = answer.sent ? 'sent' : 'failed'
  } catch {
    renewState.value = 'failed'
  }
}

/**
 * Open Google's consent page in a new tab to connect the client's agenda.
 * @returns A promise resolved once the tab is on its way to Google, or once the failure is shown.
 */
async function connectCalendar(): Promise<void> {
  if (!space.value || isCalendarBusy.value) return
  calendarError.value = null
  // Opened before the call: a tab opened after an await is blocked as a pop-up. It never sees this page.
  const tab: Window | null = window.open('about:blank', '_blank')
  if (tab) tab.opener = null
  isCalendarBusy.value = true
  try {
    const consent: AiAssistantClientCalendarConnect = await $fetch<AiAssistantClientCalendarConnect>(
      `${endpoint.value}/calendar/connect`,
      { method: 'POST' },
    )
    isAwaitingCalendar.value = true
    if (tab) tab.location.href = consent.url
    else window.location.assign(consent.url)
  } catch (error: unknown) {
    tab?.close()
    calendarError.value = failureMessage(error, 'Connexion indisponible, réessayez dans un instant.')
  } finally {
    isCalendarBusy.value = false
  }
}

/**
 * Save the booking settings the client changed.
 * @param update The changed settings only.
 * @returns A promise resolved once the API answered.
 */
async function saveCalendar(update: AiAssistantClientCalendarUpdate): Promise<void> {
  const current: AiAssistantClientSpace | null = space.value
  if (!current || isCalendarBusy.value) return
  isCalendarBusy.value = true
  calendarError.value = null
  hasSavedCalendar.value = false
  try {
    current.calendar = await $fetch<AiAssistantClientCalendar>(`${endpoint.value}/calendar`, {
      method: 'PATCH',
      body: update,
    })
    hasSavedCalendar.value = true
  } catch (error: unknown) {
    calendarError.value = failureMessage(error, 'Enregistrement impossible, réessayez dans un instant.')
  } finally {
    isCalendarBusy.value = false
  }
}

/**
 * Disconnect the agenda after a confirmation: appointments go back to requests the client confirms.
 * @returns A promise resolved once the API answered.
 */
async function disconnectCalendar(): Promise<void> {
  const current: AiAssistantClientSpace | null = space.value
  if (!current || isCalendarBusy.value) return
  const confirmed: boolean = window.confirm(
    'Déconnecter votre agenda ? Les visiteurs choisiront des demi-journées et vous confirmerez vous-même.',
  )
  if (!confirmed) return
  isCalendarBusy.value = true
  calendarError.value = null
  // « Enregistré. » belonged to the agenda that goes away.
  hasSavedCalendar.value = false
  try {
    current.calendar = await $fetch<AiAssistantClientCalendar>(`${endpoint.value}/calendar`, { method: 'DELETE' })
  } catch (error: unknown) {
    calendarError.value = failureMessage(error, 'Déconnexion impossible, réessayez dans un instant.')
  } finally {
    isCalendarBusy.value = false
  }
}

/** Reload the agenda's state when the client comes back from the Google tab; unsaved settings stay as typed. */
async function onVisibilityChange(): Promise<void> {
  const current: AiAssistantClientSpace | null = space.value
  if (document.visibilityState !== 'visible' || !isAwaitingCalendar.value || !current) return
  try {
    const fresh: AiAssistantClientSpace = await $fetch<AiAssistantClientSpace>(endpoint.value)
    current.calendar = fresh.calendar
    current.appointments = fresh.appointments
    if (fresh.calendar.status === 'connected') isAwaitingCalendar.value = false
  } catch (error: unknown) {
    showExpiredOnUnauthorized(error)
  }
}

/**
 * Unlock the portal button when the browser restores this page from its back-forward cache.
 * @param event - The page-show event.
 */
function onPageShow(event: PageTransitionEvent): void {
  if (event.persisted) isOpeningPortal.value = false
}

/** Follow the screen's width: the sidebar and the split view above 1024 px, the tab bar below. */
function onWideChange(): void {
  isWide.value = wideQuery?.matches === true
}

watch(
  load,
  (value: AiAssistantClientSpaceLoad | undefined): void => {
    if (!value) return
    state.value = value.state
    space.value = value.space
  },
  { immediate: true },
)

// A new screen starts clean: no stale « Enregistré. » nor error from the previous one.
watch(
  (): ClientSpaceSettingsScreen | null => location.value.settingsScreen,
  (): void => {
    hasSavedSettings.value = false
    settingsError.value = null
  },
)

onMounted((): void => {
  wideQuery = window.matchMedia(WIDE_QUERY)
  onWideChange()
  wideQuery.addEventListener('change', onWideChange)
  window.addEventListener('pageshow', onPageShow)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount((): void => {
  wideQuery?.removeEventListener('change', onWideChange)
  window.removeEventListener('pageshow', onPageShow)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

useHead({
  title: computed((): string => (space.value ? `Espace client · ${space.value.business_name}` : 'Espace client')),
  meta: [
    { name: 'robots', content: 'noindex, nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})
</script>

<style>
/* The client space's tokens and atoms, shared by its components (the business's colour comes from the API). */
.cs {
  --cs-bg: #f7f5f0;
  --cs-card: #ffffff;
  --cs-card-unread: #fbfaf7;
  --cs-ink: #17130d;
  --cs-dim: #6d665b;
  --cs-faint: #9a9389;
  --cs-line: #ebe7df;
  --cs-online: #2f9e5b;
  --cs-red: #c0392b;
  --cs-red-soft: #fbeae7;
  --cs-green: #1f7a45;
  --cs-green-soft: #e5f2ea;
  --cs-amber: #b26a00;
  --cs-amber-soft: #fbf0dc;
  --cs-on-accent: #ffffff;
  min-height: 100dvh;
  background: var(--cs-bg);
  color: var(--cs-ink);
  font-family: Inter, system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
}

.cs-muted {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.55;
  color: var(--cs-dim);
}

.cs-sec {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 0;
  padding: 22px 16px 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--cs-dim);
}

.cs-sec__link {
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  color: var(--cs-accent-text);
  cursor: pointer;
}

.cs-block {
  background: var(--cs-card);
  border-top: 1px solid var(--cs-line);
  border-bottom: 1px solid var(--cs-line);
}

.cs-day {
  margin: 0;
  padding: 18px 16px 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--cs-dim);
}

.cs-avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: none;
  border-radius: 50%;
  background: var(--cs-accent-tint);
  color: var(--cs-accent-text);
  font-size: 13.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.cs-avatar--lg {
  width: 52px;
  height: 52px;
  font-size: 17px;
}

.cs-avatar--portrait {
  overflow: hidden;
  background: transparent;
  box-shadow: 0 0 0 2px var(--cs-accent);
}

.cs-avatar--portrait img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cs-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 48px;
  padding: 0 16px;
  border: 1px solid var(--cs-line);
  border-radius: 10px;
  background: var(--cs-card);
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  color: var(--cs-ink);
  text-decoration: none;
  cursor: pointer;
}

.cs-btn--primary {
  border-color: var(--cs-accent-strong);
  background: var(--cs-accent-strong);
  color: var(--cs-on-accent);
}

.cs-btn--small {
  flex: none;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border-color: var(--cs-accent-strong);
  background: transparent;
  font-size: 13px;
  color: var(--cs-accent-text);
}

.cs-btn:disabled {
  cursor: default;
  opacity: 0.55;
}

.cs-quiet {
  justify-self: center;
  border: 0;
  padding: 6px;
  background: transparent;
  font: inherit;
  font-size: 13px;
  color: var(--cs-dim);
  cursor: pointer;
}

.cs-quiet:disabled {
  cursor: default;
  opacity: 0.55;
}

.cs-cell {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 50px;
  margin: 0;
  padding: 12px 16px;
  border: 0;
  border-bottom: 1px solid var(--cs-line);
  background: transparent;
  font: inherit;
  font-size: 15.5px;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.cs-cell:last-child {
  border-bottom: 0;
}

.cs-cell > span:first-of-type {
  flex: 1;
  min-width: 0;
}

.cs-cell__value {
  flex: none;
  max-width: 48%;
  font-size: 14px;
  font-weight: 500;
  color: var(--cs-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cs-cell__value--amber {
  color: var(--cs-amber);
  font-weight: 600;
}

.cs-cell__value--green {
  color: var(--cs-green);
  font-weight: 600;
}

.cs-cell__value--badge {
  display: inline-grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: var(--cs-red);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
}

.cs-text {
  margin: 0;
  padding: 14px 16px;
  font-size: 15px;
  line-height: 1.5;
}

.cs-text--dim {
  color: var(--cs-dim);
  font-size: 14.5px;
}

.cs-text b {
  font-weight: 600;
}

.cs-actions {
  position: sticky;
  bottom: 0;
  display: grid;
  gap: 8px;
  padding: 12px 16px calc(14px + env(safe-area-inset-bottom, 0px));
  background: var(--cs-card);
  border-top: 1px solid var(--cs-line);
}

.cs-head {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 16px 8px;
}

.cs-head__text {
  min-width: 0;
}

.cs-head__name {
  margin: 0;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.cs-head__meta {
  margin: 2px 0 0;
  font-size: 13.5px;
  color: var(--cs-dim);
}

.cs-head__meta b {
  font-weight: 600;
}

.cs-contact {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 8px 0 0;
  padding: 14px 16px;
  background: var(--cs-card);
  border-top: 1px solid var(--cs-line);
  border-bottom: 1px solid var(--cs-line);
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--cs-ink);
  text-decoration: none;
}

.cs-contact .cs-icon {
  color: var(--cs-accent-text);
}

.cs-contact--plain {
  font-weight: 500;
}

.cs-contact__value {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cs-contact small {
  flex: none;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--cs-accent-text);
}

.cs-todo {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 62px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--cs-line);
}

.cs-todo:last-child {
  border-bottom: 0;
}

.cs-todo__icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: none;
  border-radius: 10px;
  background: var(--cs-accent-tint);
  color: var(--cs-accent-text);
}

.cs-todo__icon--red {
  background: var(--cs-red-soft);
  color: var(--cs-red);
}

.cs-todo__icon--amber {
  background: var(--cs-amber-soft);
  color: var(--cs-amber);
}

.cs-todo__text {
  display: grid;
  flex: 1;
  min-width: 0;
  line-height: 1.3;
}

.cs-todo__text b {
  font-size: 15.5px;
  font-weight: 600;
}

.cs-todo__text span {
  font-size: 13px;
  color: var(--cs-dim);
}

.cs-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.cs-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--cs-line);
}

.cs-stat:nth-child(odd) {
  border-right: 1px solid var(--cs-line);
}

.cs-stat:nth-last-child(-n + 2) {
  border-bottom: 0;
}

.cs-stat > .cs-icon {
  width: 18px;
  height: 18px;
  color: var(--cs-faint);
}

.cs-stat > span {
  display: grid;
  line-height: 1.15;
}

.cs-stat b {
  font-size: 19px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.cs-stat > span > span {
  font-size: 12.5px;
  color: var(--cs-dim);
}

.cs-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  border: 0;
  border-bottom: 1px solid var(--cs-line);
  background: var(--cs-card);
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.cs-row:last-child {
  border-bottom: 0;
}

.cs-row--unread {
  background: var(--cs-card-unread);
}

.cs-row--active {
  background: var(--cs-accent-tint);
}

.cs-row__body {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: 4px;
}

.cs-row__top {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.cs-row__name {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cs-row__status {
  flex: none;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.cs-row__status--red {
  color: var(--cs-red);
}
.cs-row__status--accent {
  color: var(--cs-accent-text);
}
.cs-row__status--green {
  color: var(--cs-green);
}
.cs-row__status--grey {
  color: var(--cs-faint);
}
.cs-row__status--amber {
  color: var(--cs-amber);
}

.cs-row__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 13px;
  color: var(--cs-dim);
}

.cs-row__meta > span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.cs-row__meta .cs-icon {
  width: 13px;
  height: 13px;
  color: var(--cs-faint);
}

.cs-row__preview {
  font-size: 14.5px;
  line-height: 1.4;
  color: var(--cs-dim);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.cs-row--unread .cs-row__preview {
  color: var(--cs-ink);
}

.cs-seg {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  background: var(--cs-card);
  border-bottom: 1px solid var(--cs-line);
}

.cs-seg__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 0;
  border-radius: 8px;
  background: var(--cs-bg);
  font: inherit;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--cs-dim);
  cursor: pointer;
}

.cs-seg__item[aria-pressed='true'] {
  background: var(--cs-accent-strong);
  color: var(--cs-on-accent);
}

.cs-seg__item b {
  font-weight: 600;
}

.cs-photos {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--cs-line);
}

.cs-photos a {
  display: block;
  background: var(--cs-card);
}

.cs-photos img {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}

.cs-bar {
  position: sticky;
  top: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 54px;
  padding: 0 16px;
  background: var(--cs-card);
  border-bottom: 1px solid var(--cs-line);
}

.cs-bar__title {
  flex: 1;
  min-width: 0;
  font-size: 17px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cs-bar__title--brand {
  font-family: Fraunces, Georgia, serif;
  font-size: 19px;
  letter-spacing: -0.01em;
}

.cs-bar__title--center {
  flex: none;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  max-width: 55%;
}

.cs-bar__back {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-height: 44px;
  margin-left: -8px;
  padding: 0 8px 0 2px;
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 15px;
  font-weight: 500;
  color: var(--cs-accent-text);
  cursor: pointer;
}

.cs-bar__btn {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  margin-right: -8px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--cs-dim);
  cursor: pointer;
}

.cs-field {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  border: 0;
}

.cs-label {
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
}

.cs-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--cs-line);
  border-radius: 10px;
  padding: 12px 13px;
  font: inherit;
  font-size: 15.5px;
  color: var(--cs-ink);
  background: var(--cs-card);
}

.cs-input:focus {
  outline: 2px solid var(--cs-accent-strong);
  outline-offset: 1px;
}

.cs-hint {
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--cs-dim);
}

.cs-notice {
  margin: 0;
  font-size: 14px;
  color: var(--cs-ink);
}

.cs-notice--error {
  color: var(--cs-red);
}

.cs-example {
  margin: 0;
  padding: 12px 16px;
  border-bottom: 1px solid var(--cs-line);
  background: var(--cs-amber-soft);
  font-size: 13.5px;
  line-height: 1.5;
}

.cs-example__link {
  margin-left: 6px;
  font-weight: 600;
  color: var(--cs-ink);
  text-decoration: underline;
  text-underline-offset: 3px;
}

/* ---- layout ---- */
.cs-message {
  display: grid;
  gap: 14px;
  justify-items: start;
  max-width: 560px;
  margin: 0 auto;
  padding: 18vh 20px 40px;
}

.cs-message__title {
  margin: 0;
  font-family: Fraunces, Georgia, serif;
  font-size: 30px;
  font-weight: 600;
  line-height: 1.1;
}

/* Outweighs the sidebar's own scoped rule, which sets its display. */
.cs-shell > aside.cs-shell__side {
  display: none;
}

.cs-shell__main {
  min-height: 100dvh;
  padding-bottom: calc(76px + env(safe-area-inset-bottom, 0px));
}

.cs-shell__main--detail {
  padding-bottom: 0;
}

.cs-split__hint {
  padding: 28px 16px;
}

.cs-screen__body {
  display: grid;
  align-content: start;
}

.cs-screen__actions {
  display: grid;
  gap: 10px;
  padding: 0 16px 16px;
}

@media (min-width: 1024px) {
  .cs-shell {
    display: grid;
    grid-template-columns: 260px minmax(0, 1fr);
  }

  .cs-shell > aside.cs-shell__side {
    display: flex;
  }

  /* Outweighs the tab bar's own scoped rule, which sets its display. */
  .cs-shell > nav.cs-shell__tabs {
    display: none;
  }

  .cs-shell__main {
    padding-bottom: 40px;
  }

  .cs-bar--top {
    position: static;
    min-height: 64px;
    padding: 0 32px;
    background: transparent;
    border-bottom: 0;
  }

  .cs-bar--top .cs-bar__title {
    font-size: 22px;
  }

  .cs-bar--top .cs-bar__title--brand {
    font-size: 24px;
  }

  .cs-shell__main > .cs-home,
  .cs-shell__main > .cs-agenda,
  .cs-shell__main > .cs-menu,
  .cs-shell__main > .cs-screen,
  .cs-shell__main > .cs-example {
    max-width: 720px;
    margin: 0 32px;
  }

  .cs-shell__main > .cs-screen .cs-bar {
    position: static;
    background: transparent;
    border-bottom: 0;
    padding: 0;
  }

  .cs-shell__main > .cs-screen .cs-bar__title--center {
    position: static;
    transform: none;
    max-width: none;
    font-size: 22px;
  }

  .cs-block,
  .cs-contact {
    border: 1px solid var(--cs-line);
    border-radius: 12px;
    overflow: hidden;
  }

  .cs-sec {
    padding-left: 4px;
    padding-right: 4px;
  }

  .cs-day {
    padding-left: 4px;
    padding-right: 4px;
  }

  .cs-lea:not(.cs-lea--compact) {
    border: 1px solid var(--cs-line);
    border-radius: 12px;
    margin-top: 4px;
  }

  .cs-split {
    display: grid;
    grid-template-columns: 420px minmax(0, 1fr);
    min-height: calc(100dvh - 64px);
    border-top: 1px solid var(--cs-line);
  }

  .cs-split__list {
    background: var(--cs-card);
    border-right: 1px solid var(--cs-line);
  }

  .cs-split__list .cs-block {
    border: 0;
    border-radius: 0;
    border-bottom: 1px solid var(--cs-line);
  }

  .cs-split__list .cs-day {
    padding: 16px 16px 6px;
  }

  .cs-split__detail {
    background: var(--cs-card);
  }

  .cs-split__detail .cs-detail__body {
    max-width: 680px;
    padding: 12px 32px 24px;
  }

  .cs-split__detail .cs-block,
  .cs-split__detail .cs-contact {
    border: 1px solid var(--cs-line);
    border-radius: 12px;
  }

  .cs-split__detail .cs-actions {
    position: static;
    grid-template-columns: auto auto auto;
    justify-content: start;
    align-items: center;
    gap: 10px;
    max-width: 680px;
    padding: 4px 32px 32px;
    border-top: 0;
  }

  .cs-split__detail .cs-actions .cs-btn {
    padding: 0 18px;
    white-space: nowrap;
  }
}
</style>
