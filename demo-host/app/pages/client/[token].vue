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
              :error-message="requestError"
              :read-only="isExample"
              :show-back="!isWide"
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
                    <button type="button" class="cs-btn" :disabled="isOpeningBillingPortal" @click="openBillingPortal">
                      <ClientSpaceIcon name="external-link" />
                      {{ isOpeningBillingPortal ? 'Ouverture…' : 'Factures, carte bancaire, résiliation' }}
                    </button>
                    <p v-if="billingPortalError" class="cs-notice cs-notice--error">{{ billingPortalError }}</p>
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

            <div v-else-if="location.settingsScreen === 'google' && space.google_profile" class="cs-screen__body">
              <p class="cs-sec">L’adresse de {{ space.assistant_name }}</p>
              <div class="cs-block">
                <p class="cs-text">
                  Sur votre fiche Google, deux boutons peuvent mener à {{ space.assistant_name }} : « Site web » et «
                  Prendre rendez-vous ». Collez-y cette adresse : vos clients y arrivent en un geste, même sans site.
                </p>
                <pre class="cs-code">{{ space.google_profile.page_url }}</pre>
                <div class="cs-screen__actions">
                  <button type="button" class="cs-btn" @click="copyText(space.google_profile.page_url, 'link')">
                    <ClientSpaceIcon :name="copiedKey === 'link' ? 'check' : 'code'" />
                    {{ copiedKey === 'link' ? 'Copiée' : 'Copier l’adresse' }}
                  </button>
                </div>
              </div>
              <p class="cs-sec">Où la coller</p>
              <div class="cs-block">
                <ol class="cs-steps">
                  <li>
                    Cherchez votre entreprise sur Google, connecté au compte qui gère la fiche, puis « Modifier le
                    profil ».
                  </li>
                  <li>Dans « Coordonnées », champ « Site web » : collez l’adresse.</li>
                  <li>
                    Dans « Réservations » (ou « Lien de rendez-vous »), collez la même adresse, puis enregistrez. Google
                    l’affiche en quelques minutes.
                  </li>
                </ol>
                <label class="cs-check">
                  <input
                    type="checkbox"
                    :checked="space.google_profile.is_linked"
                    :disabled="isSavingGoogleProfile || isExample"
                    @change="setGoogleProfileLinked(($event.target as HTMLInputElement).checked)"
                  />
                  <span>
                    <b>C’est fait, l’adresse est sur ma fiche</b>
                    <span>{{
                      space.google_profile.is_linked && space.google_profile.linked_at_label
                        ? `Posée le ${space.google_profile.linked_at_label}.`
                        : 'Cochez quand c’est fait : l’étape passe en vert sur votre accueil.'
                    }}</span>
                  </span>
                </label>
                <p v-if="googleProfileError" class="cs-notice cs-notice--error">{{ googleProfileError }}</p>
              </div>
              <p class="cs-sec">Votre messagerie vocale</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">
                  Un appel manqué peut encore aboutir : enregistrez ce message, il renvoie vers
                  {{ space.assistant_name }}.
                </p>
                <pre class="cs-code cs-code--prose">{{ space.google_profile.voicemail_text }}</pre>
                <div class="cs-screen__actions">
                  <button
                    type="button"
                    class="cs-btn"
                    @click="copyText(space.google_profile.voicemail_text, 'voicemail')"
                  >
                    <ClientSpaceIcon :name="copiedKey === 'voicemail' ? 'check' : 'message-square'" />
                    {{ copiedKey === 'voicemail' ? 'Copié' : 'Copier le message' }}
                  </button>
                </div>
              </div>
              <p class="cs-sec">QR à imprimer</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">Carte de visite, camionnette, devis : la même adresse, à scanner.</p>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="cs-qr" v-html="space.google_profile.qr_svg"></div>
                <div class="cs-screen__actions">
                  <a class="cs-btn" :href="qrDownloadHref" :download="`qr-${space.assistant_name}.svg`">
                    <ClientSpaceIcon name="image" />Télécharger le QR
                  </a>
                </div>
              </div>
            </div>

            <div v-else-if="location.settingsScreen === 'install'" class="cs-screen__body">
              <p v-if="space.installed" class="cs-notice cs-notice--ok">
                Installée sur {{ space.installed.host }}, vue le {{ space.installed.seen_label }}.
              </p>
              <p class="cs-sec">La ligne à coller</p>
              <div class="cs-block">
                <p class="cs-text">
                  Collez cette ligne sur votre site, juste avant la fin de chaque page (la balise
                  <code>{{ BODY_END_TAG }}</code
                  >) : {{ space.assistant_name }} apparaît en bas à droite.
                </p>
                <pre class="cs-code">{{ space.embed_snippet }}</pre>
                <div class="cs-screen__actions">
                  <button type="button" class="cs-btn" @click="copyText(space.embed_snippet ?? '', 'snippet')">
                    <ClientSpaceIcon :name="copiedKey === 'snippet' ? 'check' : 'code'" />
                    {{ copiedKey === 'snippet' ? 'Copiée' : 'Copier la ligne' }}
                  </button>
                </div>
              </div>
              <p class="cs-sec">Ou à envoyer</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">
                  Quelqu’un s’occupe de votre site (une agence, un proche, votre prestataire) ? Envoyez-lui la ligne.
                  Vous pouvez aussi répondre à l’un de nos emails : on l’installe avec vous.
                </p>
                <div class="cs-screen__actions">
                  <a class="cs-btn" :href="snippetMailto"><ClientSpaceIcon name="mail" />Envoyer par email</a>
                </div>
              </div>
              <p class="cs-sec">Vérifier</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">
                  Ouvrez votre site : la bulle de {{ space.assistant_name }} doit apparaître en bas à droite de chaque
                  page. Testez-la comme un client et laissez votre numéro : la demande arrive ici, et par SMS.
                </p>
                <div v-if="space.website_url" class="cs-screen__actions">
                  <a class="cs-btn" :href="space.website_url" target="_blank" rel="noopener">
                    <ClientSpaceIcon name="external-link" />Ouvrir votre site
                  </a>
                </div>
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
                    Ce lien personnel se prolonge à chaque ouverture : tant que vous l’ouvrez au moins une fois par
                    mois, il reste valable (pour l’instant jusqu’au {{ space.link_expires_label }}). Il donne accès à
                    vos demandes : ne le transférez pas. S’il expire, vous en recevez un nouveau par email.
                  </template>
                </p>
              </div>
              <p class="cs-sec">Sur votre téléphone</p>
              <div class="cs-block">
                <p class="cs-text cs-text--dim">
                  Ajoutez cette page à l’écran d’accueil de votre téléphone (bouton Partager, puis « Sur l’écran
                  d’accueil ») : vous retrouvez vos demandes d’un geste, comme une application.
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
  AiAssistantClientRequest,
  AiAssistantClientSpaceLoad,
  AiAssistantClientSubscription,
  AiAssistantClientSubscriptionStatus,
  AiAssistantClientUnansweredEntry,
} from '~/types/AiAssistantClientSpace'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import type { ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'
import type { UseClientSpaceCalendarReturn } from '~/types/UseClientSpaceCalendar'
import type { UseClientSpaceClipboardReturn } from '~/types/UseClientSpaceClipboard'
import type { UseClientSpaceLinkReturn } from '~/types/UseClientSpaceLink'
import type { UseClientSpaceRequestsReturn } from '~/types/UseClientSpaceRequests'
import type { UseClientSpaceSettingsReturn } from '~/types/UseClientSpaceSettings'
import { useClientSpaceCalendar } from '~/composables/useClientSpaceCalendar'
import { useClientSpaceClipboard } from '~/composables/useClientSpaceClipboard'
import { useClientSpaceLink } from '~/composables/useClientSpaceLink'
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
}: UseClientSpaceCalendarReturn = useClientSpaceCalendar(link)

const { copiedKey, copyText }: UseClientSpaceClipboardReturn = useClientSpaceClipboard()

useHead({
  title: computed((): string => (space.value ? `Espace client · ${space.value.business_name}` : 'Espace client')),
  meta: [
    { name: 'robots', content: 'noindex, nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

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
  limits: 'Prix, délais, garanties',
  google: 'Votre fiche Google',
  install: 'Sur votre site',
  help: 'Aide',
}

/** From this width, the sidebar replaces the tab bar and a request opens beside the list. */
const WIDE_QUERY: string = '(min-width: 1024px)'

/** The tag the line to paste goes before, shown as text (a template cannot carry it as markup). */
const BODY_END_TAG: string = '</body>'

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

/** The QR code as a file the client saves: the API's SVG in a data URL. */
const qrDownloadHref: ComputedRef<string> = computed((): string => {
  const svg: string = space.value?.google_profile?.qr_svg ?? ''
  return svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` : ''
})

/** An email carrying the line to paste, for whoever looks after the website. */
const snippetMailto: ComputedRef<string> = computed((): string => {
  const name: string = space.value?.assistant_name ?? ''
  const business: string = space.value?.business_name ?? ''
  const subject: string = `${name}, la réceptionniste du site ${business}`
  const body: string =
    `Bonjour,\n\nPouvez-vous coller cette ligne sur le site ${business}, juste avant la balise ${BODY_END_TAG} de ` +
    `chaque page ?\n\n${space.value?.embed_snippet ?? ''}\n\nMerci !`
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
})

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

watch((): ClientSpaceSettingsScreen | null => location.value.settingsScreen, clearScreenFeedback)

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
