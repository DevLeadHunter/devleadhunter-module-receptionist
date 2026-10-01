<template>
  <div class="ia" @focusin="onFocusChange" @focusout="onFocusChange">
    <main class="ia__page">
      <header class="ia__hero">
        <p class="ia__kicker">
          {{ shortBusinessName }}<template v-if="props.assistant.city"> · {{ props.assistant.city }}</template>
        </p>
        <h1 class="ia__title">Votre réceptionniste répond à vos clients<span class="ia__dot">.</span></h1>
        <p class="ia__lede">
          Ce soir, 21h40, un client cherche « {{ searchPhrase }} » et {{ arrivalPhrase }}.
          {{ props.assistant.assistant_name }} lui répond, note sa demande et vous l’envoie par SMS.
          <strong class="ia__lede-emphasis">Essayez, comme ce client.</strong>
        </p>
        <ul class="ia__proofs" aria-label="En bref">
          <li v-for="proof in HERO_PROMISES" :key="proof.label" class="ia__proof">
            <span class="ia__proof-icon"><ClientSpaceIcon :name="proof.icon" /></span>{{ proof.label }}
          </li>
        </ul>
      </header>

      <div class="ia__stage">
        <div class="ia__side ia__side--visitor">
          <p class="ia__label">
            <b class="ia__label-who">Votre client</b> · ce soir, 21h40
            <span class="ia__live"><span class="ia__live-dot" />en direct</span>
          </p>
          <AssistantChatWindow :assistant="props.assistant" @lead-sent="onLeadSent" @example-played="onExamplePlayed" />
        </div>

        <div ref="ownerFeedSide" class="ia__side ia__side--owner">
          <p class="ia__label"><b class="ia__label-who">Vous</b> · quelques secondes plus tard</p>
          <AssistantDemoOwnerFeed
            time-label="21:43"
            :assistant-name="props.assistant.assistant_name"
            :alert-text="alertText"
            :is-example="receivedLead === null"
            :hint-text="feedHintText"
            :arrival-key="exampleArrivals"
          />
          <a v-if="receivedLead" :href="spaceUrl" class="ia__feed-link" @click="onSpaceClick">
            Voir la demande dans votre espace<ClientSpaceIcon name="arrow-right" />
          </a>
        </div>
      </div>

      <section class="ia__features" aria-label="Ce que vous recevez">
        <article v-for="feature in features" :key="feature.title" class="ia__feature">
          <span class="ia__feature-icon"><ClientSpaceIcon :name="feature.icon" /></span>
          <h2 class="ia__feature-title">{{ feature.title }}</h2>
          <p class="ia__feature-text">{{ feature.text }}</p>
        </article>
      </section>

      <section v-if="closedHours" class="ia__estimate" aria-label="Quand c’est fermé">
        <b class="ia__estimate-figure">≈ {{ closedHours.estimated_requests }}</b>
        <p class="ia__estimate-text">
          <b class="ia__estimate-title">demandes par mois arrivent quand c’est fermé</b>
          <span
            >{{ closedHours.closed_share_pct }} % du temps entre 7 h et 22 h. {{ props.assistant.assistant_name }} y
            répond.</span
          >
        </p>
      </section>

      <section class="ia__space" aria-labelledby="ia-space-title">
        <div class="ia__space-text">
          <p class="ia__eyebrow">Votre espace</p>
          <h2 id="ia-space-title" class="ia__space-title">Vous gardez la main</h2>
          <ul class="ia__checks">
            <li v-for="item in spacePoints" :key="item.label" class="ia__check">
              <span class="ia__check-icon"><ClientSpaceIcon :name="item.icon" /></span>{{ item.label }}
            </li>
          </ul>
          <a :href="spaceUrl" class="ia__space-button" @click="onSpaceClick">
            Découvrir votre espace<ClientSpaceIcon name="arrow-right" />
          </a>
        </div>
        <a :href="spaceUrl" class="ia__space-figure" tabindex="-1" @click="onSpaceClick">
          <img
            class="ia__space-image"
            src="/showroom/espace-client.webp"
            alt="Votre espace : les demandes, l’activité de la réceptionniste et ce qu’il reste à faire"
            width="1400"
            height="875"
            loading="lazy"
          />
        </a>
      </section>

      <section class="ia__never" aria-labelledby="ia-never-title">
        <h2 id="ia-never-title" class="ia__never-title">Ce que {{ props.assistant.assistant_name }} ne fait jamais</h2>
        <ul class="ia__never-list">
          <li v-for="item in neverPoints" :key="item.label" class="ia__never-item">
            <span class="ia__never-icon"><ClientSpaceIcon :name="item.icon" /></span>{{ item.label }}
          </li>
        </ul>
      </section>

      <section v-if="priceLabel" class="ia__offer" aria-label="L’offre">
        <p class="ia__offer-price">
          <b class="ia__offer-amount">{{ priceLabel }}</b
          ><span class="ia__offer-period">par mois</span>
        </p>
        <ul class="ia__offer-terms">
          <li v-for="term in OFFER_TERMS" :key="term" class="ia__offer-term">
            <ClientSpaceIcon name="check" />{{ term }}
          </li>
        </ul>
        <DemoCtaLink class="ia__offer-cta" :href="subscribeUrl"
          >Je garde {{ props.assistant.assistant_name }}</DemoCtaLink
        >
      </section>

      <p v-if="ownerNameLabel" class="ia__signature">
        Réceptionniste préparé{{ femininSuffix }} pour {{ shortBusinessName }} par {{ ownerNameLabel }}, développeur
        web.
      </p>
    </main>

    <div class="ia__banner" :class="{ 'ia__banner--hidden': isComposerFocused }">
      <AssistantContactBanner
        :slug="props.assistant.slug"
        :business-name="props.assistant.business_name"
        :owner-name="props.assistant.owner_name ?? null"
        :owner-photo-url="props.assistant.owner_profile_photo_url ?? null"
        :owner-phone="props.assistant.owner_contact_phone ?? null"
        :owner-email="props.assistant.owner_contact_email ?? null"
        :status="props.assistant.status"
        :accent-color="props.assistant.accent_color"
      />
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import type { AiAssistantClosedHours, AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type {
  AssistantDemoPageFeature,
  AssistantDemoPagePoint,
  AssistantDemoPageProps,
} from '~/types/AssistantDemoPage'
import { computed, onMounted, ref } from 'vue'
import AssistantChatWindow from '~/components/AssistantChatWindow.vue'
import AssistantDemoOwnerFeed from '~/components/AssistantDemoOwnerFeed.vue'
import DemoCtaLink from '~/components/DemoCtaLink.vue'
import { captureDemoEvent, useDemoTracking } from '~/composables/useDemoTracking'
import { AssistantDemoScenarioUtils } from '~/utils/AssistantDemoScenarioUtils'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'

const HERO_PROMISES: AssistantDemoPagePoint[] = [
  { icon: 'clock', label: 'Répond 24 h sur 24, 7 jours sur 7' },
  { icon: 'message-square', label: 'Vous prévient par SMS' },
  { icon: 'camera', label: 'Note la photo et le numéro' },
]

const OFFER_TERMS: string[] = ['Sans engagement', 'Mise en place incluse', 'Premier mois satisfait ou remboursé']

const props: AssistantDemoPageProps = defineProps({
  assistant: { type: Object as PropType<AiAssistantConfig>, required: true },
  isJustSubscribed: { type: Boolean, default: false },
})

const route: ReturnType<typeof useRoute> = useRoute()
const config: ReturnType<typeof useRuntimeConfig> = useRuntimeConfig()
const { init: initTracking }: ReturnType<typeof useDemoTracking> = useDemoTracking()

/** The request the visitor sent from the conversation, once there is one. */
const receivedLead: Ref<AssistantLeadSummary | null> = ref(null)
/** True while the visitor types in the conversation: the contact pill steps aside (it would cover the keys). */
const isComposerFocused: Ref<boolean> = ref(false)
/** The business's side, scrolled into view on a small screen once a request lands on it. */
const ownerFeedSide: Ref<HTMLElement | null> = ref(null)
/** How many times the played example has ended: each one makes the example notification land again. */
const exampleArrivals: Ref<number> = ref(0)

const shortBusinessName: ComputedRef<string> = computed((): string =>
  BusinessNameUtils.short(props.assistant.business_name),
)

/** Owner name for the signature line (empty when the owner set no name). */
const ownerNameLabel: ComputedRef<string> = computed((): string => (props.assistant.owner_name ?? '').trim())

/** « e » after a word agreeing with a feminine persona, nothing for a masculine one. */
const femininSuffix: ComputedRef<string> = computed((): string =>
  props.assistant.assistant_gender === 'masculine' ? '' : 'e',
)

/** What the customer types in Google (« couvreur Rennes »). */
const searchPhrase: ComputedRef<string> = computed((): string => {
  const trade: string = AssistantDemoScenarioUtils.searchWord(props.assistant.trade_label ?? null)
  const city: string = (props.assistant.city ?? '').trim()
  return city ? `${trade} ${city}` : trade
})

/** How the customer reaches the business tonight: its website, or its Google listing when it has none. */
const arrivalPhrase: ComputedRef<string> = computed((): string =>
  props.assistant.has_website === false ? 'tombe sur votre fiche Google' : 'ouvre votre site',
)

const features: ComputedRef<AssistantDemoPageFeature[]> = computed((): AssistantDemoPageFeature[] => [
  { icon: 'bell', title: 'Un SMS tout de suite', text: 'Le besoin, l’urgence, le numéro et la photo.' },
  {
    icon: 'calendar-check',
    title: 'Les rendez-vous dans votre agenda',
    text: 'Google Agenda, et un rappel au client la veille.',
  },
  {
    icon: 'chart-column',
    title: 'Un rapport chaque mois',
    text: `Ce que ${props.assistant.assistant_name} vous a apporté : demandes, devis, clients gagnés.`,
  },
])

const spacePoints: ComputedRef<AssistantDemoPagePoint[]> = computed((): AssistantDemoPagePoint[] => [
  { icon: 'inbox', label: 'Chaque demande, avec le numéro et la photo' },
  { icon: 'chart-column', label: `L’activité de ${props.assistant.assistant_name}, jour par jour` },
  { icon: 'sliders-horizontal', label: 'Ses réponses : vos prix, vos délais, vos horaires' },
])

const neverPoints: AssistantDemoPagePoint[] = [
  { icon: 'x', label: 'Donner un prix que vous n’avez pas fixé' },
  { icon: 'x', label: 'Promettre une intervention à votre place' },
  { icon: 'x', label: 'Se faire passer pour une personne' },
  { icon: 'x', label: 'Garder les photos au-delà du devis' },
]

/** The SMS on the business's phone: the example of the trade, then the visitor's own request. */
const alertText: ComputedRef<string> = computed((): string =>
  receivedLead.value
    ? AssistantDemoScenarioUtils.alertText(receivedLead.value)
    : AssistantDemoScenarioUtils.exampleAlertText(props.assistant.trade_label ?? null),
)

const feedHintText: ComputedRef<string> = computed((): string => {
  if (!receivedLead.value && exampleArrivals.value > 0) {
    return 'Voilà ce que vous auriez reçu. À vous : écrivez dans la conversation comme ce client le ferait.'
  }
  if (!receivedLead.value) {
    return `Terminez la conversation avec ${props.assistant.assistant_name} : ce SMS devient le vôtre.`
  }
  const stored: string = receivedLead.value.hasPhoto ? 'La fiche complète et la photo sont' : 'La fiche complète est'
  return `Reçu à 21h43. ${stored} dans votre espace.`
})

/**
 * The monthly price a demo shows (« 79 € », formatted by the API like the emails); empty right after the checkout
 * (the payment may not be recorded yet).
 */
const priceLabel: ComputedRef<string> = computed((): string => {
  const label: string | null | undefined = props.assistant.monthly_price_label
  if (!label || props.isJustSubscribed) return ''
  return label
})

/** The prospect's own space, or the example space when the API offers none; an internal visit stays internal. */
const spaceUrl: ComputedRef<string> = computed((): string => {
  const isInternalVisit: boolean = route.query.internal === '1'
  if (props.assistant.has_demo_space) {
    return `/ia/${props.assistant.slug}/espace${isInternalVisit ? '?internal=1' : ''}`
  }
  return `/client/exemple?demo=${props.assistant.slug}${isInternalVisit ? '&internal=1' : ''}`
})

/** The permanent subscription link: each click opens a fresh Stripe Checkout. */
const subscribeUrl: ComputedRef<string> = computed(
  (): string => `${config.public.apiBase}/api/v1/ai-assistants/public/${props.assistant.slug}/subscribe?interval=month`,
)

/** The estimate of a demo, shown from two requests a month while the business is closed (null otherwise). */
const closedHours: ComputedRef<AiAssistantClosedHours | null> = computed((): AiAssistantClosedHours | null => {
  const estimate: AiAssistantClosedHours | null | undefined = props.assistant.closed_hours
  return estimate && estimate.estimated_requests >= 2 ? estimate : null
})

/**
 * Show on the business's side the request the visitor just sent from the conversation.
 * @param summary - What the widget sent.
 */
function onLeadSent(summary: AssistantLeadSummary): void {
  receivedLead.value = summary
  revealOwnerFeed()
}

/** The prospect opens its space (or the example): the sign that the « after » matters to them. */
function onSpaceClick(): void {
  captureDemoEvent(props.assistant.has_demo_space ? 'assistant_demo_space_opened' : 'assistant_space_example_opened')
}

/** The scripted conversation has run: the example SMS lands again on the business's side. */
function onExamplePlayed(): void {
  exampleArrivals.value += 1
  revealOwnerFeed()
}

/** On a small screen, scroll the business's side into view once something lands on it. */
function revealOwnerFeed(): void {
  if (typeof window !== 'undefined' && window.innerWidth < 900) {
    ownerFeedSide.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

/**
 * Track whether the focus sits in a field of the inline widget.
 * @param event - The focusin or focusout event bubbling from the page.
 */
function onFocusChange(event: FocusEvent): void {
  const target: EventTarget | null = event.type === 'focusin' ? event.target : event.relatedTarget
  isComposerFocused.value =
    target instanceof HTMLElement &&
    (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) &&
    target.closest('.ai-widget--inline') !== null
}

onMounted((): void => {
  initTracking(
    props.assistant.slug,
    props.assistant.status,
    DemoBeaconUtils.variantFromQuery(route.query.v),
    DemoBeaconUtils.channelFromQuery(route.query.src),
    'assistant',
  )
})
</script>

<style scoped>
.ia {
  --ia-tint: color-mix(in srgb, var(--a-accent) 14%, #fff);
  --ia-radius: 18px;
  --ia-raised: 0 1px 2px rgba(23, 19, 13, 0.05), 0 14px 32px -22px rgba(23, 19, 13, 0.3);
  overflow-x: clip;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ia__page {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding-inline: 24px;
  padding-block: clamp(36px, 7vh, 80px) 48px;
  display: flex;
  flex-direction: column;
}

.ia__kicker {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ia-ink-dim);
}
.ia__kicker::before {
  content: '';
  width: 26px;
  height: 2px;
  background: var(--a-accent);
}
.ia__title {
  margin: 18px 0 0;
  max-width: 18ch;
  font-size: clamp(34px, 6vw, 60px);
  font-weight: 750;
  line-height: 1.04;
  letter-spacing: -0.035em;
  text-wrap: balance;
}
.ia__dot {
  color: var(--a-accent);
}
.ia__lede {
  margin: 18px 0 0;
  max-width: 60ch;
  font-size: clamp(15.5px, 2.1vw, 18px);
  line-height: 1.6;
  color: var(--ia-ink-dim);
}
.ia__lede-emphasis {
  color: var(--ia-ink);
  font-weight: 650;
}
.ia__proofs {
  margin: 22px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ia__proof {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-height: 40px;
  padding: 0 14px 0 6px;
  border: 1px solid var(--ia-line);
  border-radius: 999px;
  background: var(--ia-card);
  font-size: 14px;
  font-weight: 600;
}
.ia__proof-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--ia-tint);
  color: var(--a-accent-text);
}
.ia__proof-icon .cs-icon {
  width: 16px;
  height: 16px;
}

.ia__label {
  margin: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ia-ink-dim);
}
.ia__label-who {
  color: var(--ia-ink);
}
.ia__live {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--ia-ink-dim);
}
.ia__live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3fb950;
  box-shadow: 0 0 0 3px rgba(63, 185, 80, 0.2);
}
.ia__stage {
  position: relative;
  margin-top: clamp(28px, 5vh, 44px);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 30px;
}
@media (min-width: 900px) {
  .ia__stage {
    grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
    gap: 32px;
    align-items: start;
  }
}
.ia__stage::before {
  content: '';
  position: absolute;
  inset: 6% -6% 6% -6%;
  background: radial-gradient(closest-side, color-mix(in srgb, var(--a-accent) 18%, transparent), transparent 74%);
  z-index: 0;
  pointer-events: none;
}
.ia__side {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 14px;
  min-width: 0;
}
.ia__side--owner {
  align-self: start;
}
@media (min-width: 900px) {
  .ia__side--owner {
    position: sticky;
    top: 24px;
  }
}
.ia__feed-link {
  justify-self: center;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 18px;
  border-radius: 999px;
  background: var(--a-accent-strong);
  color: #fff;
  font-size: 14.5px;
  font-weight: 650;
  text-decoration: none;
}
.ia__feed-link .cs-icon {
  width: 17px;
  height: 17px;
}
.ia__banner--hidden :deep(.contact-banner) {
  opacity: 0;
  pointer-events: none;
}

.ia__features {
  margin-top: clamp(36px, 6vh, 56px);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}
@media (min-width: 720px) {
  .ia__features {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }
}
.ia__feature {
  display: grid;
  align-content: start;
  gap: 6px;
  padding: 22px;
  border: 1px solid var(--ia-line-soft);
  border-radius: var(--ia-radius);
  background: #fff;
  box-shadow: var(--ia-raised);
}
.ia__feature-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin-bottom: 10px;
  border-radius: 12px;
  background: var(--a-accent-strong);
  color: #fff;
}
.ia__feature-icon .cs-icon {
  width: 21px;
  height: 21px;
}
.ia__feature-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: 1.25;
}
.ia__feature-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ia-ink-dim);
}
@media (max-width: 719px) {
  .ia__feature {
    grid-template-columns: 44px minmax(0, 1fr);
    column-gap: 14px;
    row-gap: 2px;
    padding: 16px;
  }
  .ia__feature-icon {
    grid-row: span 2;
    margin-bottom: 0;
  }
  .ia__feature-title {
    font-size: 16px;
  }
}

.ia__estimate {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 22px;
  padding: 20px 24px;
  border-radius: var(--ia-radius);
  background: var(--ia-ink);
  color: #fff;
}
.ia__estimate-figure {
  font-size: clamp(40px, 7vw, 56px);
  font-weight: 750;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
  color: var(--ia-tint);
}
.ia__estimate-text {
  display: grid;
  gap: 4px;
  flex: 1 1 260px;
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.72);
}
.ia__estimate-title {
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: #fff;
}

.ia__space {
  margin-top: clamp(36px, 6vh, 56px);
  display: grid;
  gap: 24px;
  align-items: center;
  padding: clamp(20px, 3vw, 32px);
  border: 1px solid var(--ia-line-soft);
  border-radius: 24px;
  background: #fff;
  box-shadow: var(--ia-raised);
}
@media (min-width: 900px) {
  .ia__space {
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.5fr);
    gap: 36px;
  }
}
.ia__space-text {
  display: grid;
  justify-items: start;
  gap: 14px;
}
.ia__eyebrow {
  margin: 0;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--a-accent-text);
}
.ia__space-title {
  margin: 0;
  font-size: clamp(26px, 3.6vw, 34px);
  font-weight: 750;
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.ia__checks,
.ia__never-list,
.ia__offer-terms {
  margin: 0;
  padding: 0;
  list-style: none;
}
.ia__checks {
  display: grid;
  gap: 10px;
}
.ia__check {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.4;
}
.ia__check-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 9px;
  background: var(--ia-tint);
  color: var(--a-accent-text);
}
.ia__check-icon .cs-icon {
  width: 17px;
  height: 17px;
}
.ia__space-button {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  margin-top: 6px;
  padding: 0 22px;
  border-radius: 999px;
  background: var(--a-accent-strong);
  color: #fff;
  font-size: 15.5px;
  font-weight: 650;
  text-decoration: none;
  transition:
    transform 0.15s,
    box-shadow 0.15s;
}
.ia__space-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px -14px var(--a-accent-strong);
}
.ia__space-button:focus-visible {
  outline: 3px solid var(--ia-tint);
  outline-offset: 2px;
}
.ia__space-button .cs-icon {
  width: 18px;
  height: 18px;
}
.ia__space-figure {
  display: block;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--ia-line);
  box-shadow: 0 24px 60px -34px rgba(23, 19, 13, 0.45);
  transition: transform 0.15s;
}
.ia__space-figure:hover {
  transform: translateY(-2px);
}
.ia__space-image {
  display: block;
  width: 100%;
  height: auto;
}

.ia__never {
  margin-top: 16px;
  padding: 20px 24px;
  border: 1px solid var(--ia-line-soft);
  border-radius: var(--ia-radius);
  background: #fff;
}
.ia__never-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.015em;
}
.ia__never-list {
  margin-top: 14px;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px 24px;
}
@media (min-width: 720px) {
  .ia__never-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.ia__never-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14.5px;
  line-height: 1.4;
}
.ia__never-icon {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex: none;
  border-radius: 50%;
  background: #f6e3df;
  color: #a33a2c;
}
.ia__never-icon .cs-icon {
  width: 14px;
  height: 14px;
}

.ia__offer {
  margin-top: clamp(36px, 6vh, 56px);
  display: grid;
  justify-items: center;
  gap: 16px;
  padding: clamp(24px, 4vw, 36px);
  border: 1px solid var(--ia-line-soft);
  border-radius: 24px;
  background: #fff;
  box-shadow: var(--ia-raised);
  text-align: center;
}
.ia__offer-price {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0;
}
.ia__offer-amount {
  font-size: clamp(44px, 7vw, 60px);
  font-weight: 750;
  letter-spacing: -0.04em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.ia__offer-period {
  font-size: 17px;
  font-weight: 500;
  color: var(--ia-ink-dim);
}
.ia__offer-terms {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px 22px;
}
.ia__offer-term {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 14.5px;
  font-weight: 500;
}
.ia__offer-term .cs-icon {
  width: 17px;
  height: 17px;
  color: #2f8a4c;
}
.ia__offer-cta {
  width: min(100%, 460px);
}

.ia__signature {
  margin: clamp(36px, 7vh, 64px) 0 0;
  padding-top: 18px;
  border-top: 1px solid var(--ia-line);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ia-ink-dim);
  text-align: center;
}
@media (max-width: 640px) {
  .ia__page {
    padding-inline: 18px;
    /* Room to scroll the scene above the contact pill, which floats over the bottom corner. */
    padding-bottom: 100px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ia__space-button,
  .ia__space-figure {
    transition: none;
  }
}
</style>
