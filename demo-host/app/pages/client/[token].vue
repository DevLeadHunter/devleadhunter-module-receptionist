<template>
  <div class="cs" :style="accentStyle">
    <header class="cs__top">
      <span class="cs__logo">{{ shortBusinessName }}</span>
      <span class="cs__tag">Espace client</span>
    </header>

    <main v-if="state === 'loading'" class="cs__main cs__main--message">
      <p class="cs-muted">Chargement…</p>
    </main>

    <main v-else-if="state === 'expired'" class="cs__main cs__main--message">
      <h1 class="cs__title">Ce lien a expiré</h1>
      <p class="cs-muted">Pour protéger vos demandes, un lien ne dure que 30 jours.</p>
      <button v-if="renewState === 'idle'" type="button" class="cs-button" @click="renewLink">
        Recevoir un nouveau lien par email
      </button>
      <p v-else-if="renewState === 'sending'" class="cs-muted">Envoi…</p>
      <p v-else-if="renewState === 'sent'" class="cs__notice">
        C’est envoyé : ouvrez le nouveau lien depuis votre boîte mail.
      </p>
      <p v-else class="cs__notice cs__notice--error">
        Envoi impossible pour le moment : répondez à l’un de nos emails, on vous renvoie un lien.
      </p>
    </main>

    <main v-else-if="!space" class="cs__main cs__main--message">
      <h1 class="cs__title">{{ state === 'unavailable' ? 'Espace indisponible' : 'Lien invalide' }}</h1>
      <p class="cs-muted">
        {{
          state === 'unavailable'
            ? 'Réessayez dans quelques minutes.'
            : 'Ce lien n’ouvre aucun espace. Utilisez le dernier lien reçu par email ou par SMS.'
        }}
      </p>
    </main>

    <main v-else class="cs__main">
      <section class="cs__hero">
        <span class="cs__portrait">
          <AssistantAvatar :url="portraitUrl" :fallback-url="portraitFallbackUrl" :alt="space.assistant_name" />
        </span>
        <div class="cs__hero-text">
          <p class="cs__kicker">{{ space.assistant_name }} · votre réceptionniste</p>
          <h1 class="cs__title">{{ heroTitle }}</h1>
        </div>
      </section>

      <ClientSpaceRequests
        :requests="space.requests"
        :pending-count="space.pending_count"
        :busy-request-id="busyRequestId"
        @handled="markHandled"
      />
      <p v-if="actionError" class="cs__notice cs__notice--error">{{ actionError }}</p>

      <ClientSpaceAppointments v-if="space.appointments.length > 0" :appointments="space.appointments" />

      <ClientSpaceReport :report="space.report" :assistant-name="space.assistant_name" />

      <ClientSpaceSettings
        :settings="space.settings"
        :language-options="space.language_options"
        :is-saving="isSavingSettings"
        :error-message="settingsError"
        :has-saved="hasSavedSettings"
        @save="saveSettings"
      />

      <ClientSpaceSection
        title="Abonnement"
        :meta="space.subscription ? SUBSCRIPTION_LABELS[space.subscription.status] : null"
      >
        <p v-if="!space.subscription" class="cs-muted">Aucun abonnement enregistré.</p>
        <template v-else>
          <p class="cs__line">
            <strong>{{ space.subscription.price_label }}</strong>
            <span v-if="periodLine"> · {{ periodLine }}</span>
          </p>
          <button
            v-if="space.subscription.can_manage"
            type="button"
            class="cs-button cs-button--outline"
            :disabled="isOpeningPortal"
            @click="openPortal"
          >
            {{ isOpeningPortal ? 'Ouverture…' : 'Factures, carte bancaire, résiliation' }}
          </button>
          <p v-if="portalError" class="cs__notice cs__notice--error">{{ portalError }}</p>
        </template>
      </ClientSpaceSection>

      <ClientSpaceCalendar
        :calendar="space.calendar"
        :assistant-name="space.assistant_name"
        :is-busy="isCalendarBusy"
        :error-message="calendarError"
        :has-saved="hasSavedCalendar"
        @connect="connectCalendar"
        @save="saveCalendar"
        @disconnect="disconnectCalendar"
      />

      <p class="cs__foot">
        Lien personnel, valable jusqu’au {{ space.link_expires_label }}. Ne le transférez pas : il donne accès à vos
        demandes.
      </p>
    </main>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type {
  AiAssistantClientCalendar,
  AiAssistantClientCalendarConnect,
  AiAssistantClientCalendarUpdate,
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
} from '~/types/AiAssistantClientSpace'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantAvatarUtils } from '~/utils/AssistantAvatarUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'

const SUBSCRIPTION_LABELS: Record<AiAssistantClientSubscriptionStatus, string> = {
  incomplete: 'En attente',
  active: 'Actif',
  past_due: 'Paiement en attente',
  canceled: 'Résilié',
}

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

const state: Ref<AiAssistantClientSpaceState> = ref('loading')
const space: Ref<AiAssistantClientSpace | null> = ref(null)
const busyRequestId: Ref<number | null> = ref(null)
const actionError: Ref<string | null> = ref(null)
const isSavingSettings: Ref<boolean> = ref(false)
const settingsError: Ref<string | null> = ref(null)
const hasSavedSettings: Ref<boolean> = ref(false)
const isOpeningPortal: Ref<boolean> = ref(false)
const portalError: Ref<string | null> = ref(null)
const renewState: Ref<AiAssistantClientRenewState> = ref('idle')
const isCalendarBusy: Ref<boolean> = ref(false)
const calendarError: Ref<string | null> = ref(null)
const hasSavedCalendar: Ref<boolean> = ref(false)
// Google opened in another tab: the space reloads when the client comes back to this one.
const isAwaitingCalendar: Ref<boolean> = ref(false)

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

const accentStyle: ComputedRef<Record<string, string>> = computed((): Record<string, string> => ({
  '--a-accent': space.value?.accent_color || AssistantAccentUtils.FALLBACK_ACCENT,
  '--ai-accent-tint': AssistantAccentUtils.palette(space.value?.accent_color).tint,
}))

const shortBusinessName: ComputedRef<string> = computed((): string =>
  BusinessNameUtils.short(space.value?.business_name ?? ''),
)

const heroTitle: ComputedRef<string> = computed((): string => {
  const pendingCount: number = space.value?.pending_count ?? 0
  if (pendingCount === 0) return 'Tout est à jour.'
  return pendingCount === 1 ? '1 demande à traiter.' : `${pendingCount} demandes à traiter.`
})

const periodLine: ComputedRef<string> = computed((): string => {
  const subscription: AiAssistantClientSubscription | null = space.value?.subscription ?? null
  if (!subscription?.period_end_label) return ''
  if (subscription.status === 'canceled' || subscription.cancel_scheduled) {
    return `résiliation prévue, accès jusqu’au ${subscription.period_end_label}`
  }
  if (subscription.status === 'past_due') return `échéance du ${subscription.period_end_label}`
  return `prochain renouvellement le ${subscription.period_end_label}`
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
 * Mark a request handled and update its row and the pending count.
 * @param requestId The request.
 * @returns A promise resolved once the API answered.
 */
async function markHandled(requestId: number): Promise<void> {
  const current: AiAssistantClientSpace | null = space.value
  if (!current || busyRequestId.value !== null) return
  busyRequestId.value = requestId
  actionError.value = null
  try {
    const updated: AiAssistantClientRequest = await $fetch<AiAssistantClientRequest>(
      `${endpoint.value}/requests/${requestId}/handled`,
      { method: 'POST' },
    )
    const wasPending: boolean = current.requests.some(
      (item: AiAssistantClientRequest): boolean => item.id === requestId && item.status === 'new',
    )
    current.requests = current.requests.map((item: AiAssistantClientRequest): AiAssistantClientRequest =>
      item.id === requestId ? updated : item,
    )
    if (wasPending && updated.status !== 'new') current.pending_count = Math.max(0, current.pending_count - 1)
  } catch (error: unknown) {
    if (!showExpiredOnUnauthorized(error)) {
      actionError.value = 'La demande n’a pas pu être mise à jour, réessayez dans un instant.'
    }
  } finally {
    busyRequestId.value = null
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

watch(
  load,
  (value: AiAssistantClientSpaceLoad | undefined): void => {
    if (!value) return
    state.value = value.state
    space.value = value.space
  },
  { immediate: true },
)

onMounted((): void => {
  window.addEventListener('pageshow', onPageShow)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount((): void => {
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
.cs {
  --cs-paper: #f7f3ec;
  --cs-ink: #17130d;
  --cs-ink-dim: #6d665b;
  --cs-line: rgba(23, 19, 13, 0.12);
  --cs-card: #fffdf9;
  --cs-danger: #9f3a2f;
  --cs-accent-soft: color-mix(in srgb, var(--a-accent) 16%, #fff);
  --cs-on-ink: #fff;
}

.cs-muted {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--cs-ink-dim);
}

.cs-button {
  cursor: pointer;
  border: 1px solid var(--cs-ink);
  border-radius: 10px;
  padding: 10px 16px;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--cs-on-ink);
  background: var(--cs-ink);
}

.cs-button--outline {
  color: var(--cs-ink);
  background: transparent;
}

.cs-button:disabled {
  cursor: default;
  opacity: 0.5;
}

.cs-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--cs-line);
  border-radius: 10px;
  padding: 10px 12px;
  font: inherit;
  font-size: 15px;
  color: var(--cs-ink);
  background: #fff;
}

.cs-input:focus {
  outline: 2px solid color-mix(in srgb, var(--a-accent) 55%, transparent);
  outline-offset: 1px;
}

.cs-field {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  border: 0;
}

.cs-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--cs-ink);
}
</style>

<style scoped>
.cs {
  min-height: 100dvh;
  background: var(--cs-paper);
  color: var(--cs-ink);
  font-family: Inter, system-ui, sans-serif;
}

.cs__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--cs-line);
  padding: 18px 20px;
}

.cs__logo {
  overflow: hidden;
  font-family: Fraunces, Georgia, serif;
  font-size: 1.25rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cs__tag {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--cs-ink-dim);
}

.cs__main {
  display: grid;
  gap: 18px;
  max-width: 760px;
  margin: 0 auto;
  padding: 28px 16px 56px;
}

.cs__main--message {
  justify-items: start;
  padding-top: 18vh;
}

.cs__hero {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 18px;
}
.cs__portrait {
  display: block;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  box-shadow: 0 0 0 2px var(--a-accent);
}
.cs__hero-text {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.cs__kicker {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--cs-ink-dim);
}

.cs__kicker::before {
  content: '';
  width: 22px;
  height: 2px;
  background: var(--a-accent);
}

.cs__title {
  margin: 0;
  font-family: Fraunces, Georgia, serif;
  font-size: clamp(30px, 6vw, 44px);
  font-weight: 600;
  line-height: 1.08;
  letter-spacing: -0.015em;
}

.cs__line {
  margin: 0 0 14px;
  font-size: 15px;
}

.cs__notice {
  margin: 0;
  font-size: 14px;
  color: var(--cs-ink);
}

.cs__notice--error {
  color: var(--cs-danger);
}

.cs__foot {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: var(--cs-ink-dim);
}
</style>
