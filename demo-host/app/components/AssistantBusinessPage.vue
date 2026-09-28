<template>
  <main class="business-page">
    <header class="business-page__header">
      <p v-if="tradeLine" class="business-page__trade">{{ tradeLine }}</p>
      <h1 class="business-page__name">{{ businessName }}</h1>
      <p v-if="ratingLabel" class="business-page__rating">{{ ratingLabel }}</p>
      <p class="business-page__intro">
        Une question, une photo, un rendez-vous : écrivez à {{ assistantName }}, {{ pronoun }} vous répond à toute
        heure.
      </p>
      <p v-if="openStatusLabel" class="business-page__status" :class="{ 'business-page__status--open': isOpenNow }">
        <span class="business-page__status-dot" aria-hidden="true" />{{ openStatusLabel }}
      </p>
    </header>

    <div class="business-page__layout" :class="{ 'business-page__layout--single': !hasContactDetails }">
      <AssistantChatWindow :assistant="props.assistant" />

      <aside v-if="hasContactDetails" class="business-page__contact" aria-label="Coordonnées">
        <section v-if="phoneNumber" class="business-page__block">
          <h2 class="business-page__block-title">Téléphone</h2>
          <a v-if="phoneHref" :href="phoneHref" class="business-page__phone business-page__phone--link">{{
            phoneNumber
          }}</a>
          <p v-else class="business-page__phone">{{ phoneNumber }}</p>
        </section>
        <section v-if="address" class="business-page__block">
          <h2 class="business-page__block-title">Adresse</h2>
          <a :href="addressMapHref" class="business-page__address" target="_blank" rel="noopener">{{ address }}</a>
        </section>
        <section v-if="openingHours.length > 0" class="business-page__block">
          <h2 class="business-page__block-title">Horaires</h2>
          <OpeningHoursList :rows="openingHours" />
        </section>
      </aside>
    </div>

    <footer class="business-page__footer">
      {{ assistantName }} est {{ roleLabel }} de {{ businessName }} : {{ pronoun }} note votre demande et la transmet
      aussitôt.
    </footer>
  </main>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import AssistantChatWindow from '~/components/AssistantChatWindow.vue'
import OpeningHoursList from '~/components/OpeningHoursList.vue'
import type { AiAssistantConfig } from '~/types/AiAssistant'
import type { AssistantBusinessPageProps } from '~/types/AssistantBusinessPage'
import type { AiAssistantOpeningHoursRow } from '~/types/AiAssistantPublicBusiness'
import { BusinessNameUtils } from '~/utils/BusinessNameUtils'
import { ContactLinkUtils } from '~/utils/ContactLinkUtils'

const props: AssistantBusinessPageProps = defineProps({
  assistant: { type: Object as PropType<AiAssistantConfig>, required: true },
})

const businessName: ComputedRef<string> = computed((): string => BusinessNameUtils.short(props.assistant.business_name))

const assistantName: ComputedRef<string> = computed((): string => props.assistant.assistant_name)

const tradeLine: ComputedRef<string> = computed((): string =>
  BusinessNameUtils.tradeAndCity(props.assistant.trade_label ?? null, props.assistant.city ?? null),
)

const isMasculinePersona: ComputedRef<boolean> = computed(
  (): boolean => props.assistant.assistant_gender === 'masculine',
)

const pronoun: ComputedRef<string> = computed((): string => (isMasculinePersona.value ? 'il' : 'elle'))

const roleLabel: ComputedRef<string> = computed((): string =>
  isMasculinePersona.value ? 'le réceptionniste IA' : 'la réceptionniste IA',
)

const phoneNumber: ComputedRef<string | null> = computed((): string | null => props.assistant.business?.phone ?? null)

const phoneHref: ComputedRef<string | null> = computed((): string | null =>
  phoneNumber.value ? ContactLinkUtils.href(phoneNumber.value) : null,
)

const address: ComputedRef<string | null> = computed((): string | null => props.assistant.business?.address ?? null)

const addressMapHref: ComputedRef<string> = computed((): string =>
  ContactLinkUtils.mapHref(`${businessName.value}, ${address.value ?? ''}`),
)

const openingHours: ComputedRef<AiAssistantOpeningHoursRow[]> = computed(
  (): AiAssistantOpeningHoursRow[] => props.assistant.business?.opening_hours ?? [],
)

const hasContactDetails: ComputedRef<boolean> = computed(
  (): boolean => Boolean(phoneNumber.value || address.value) || openingHours.value.length > 0,
)

const ratingLabel: ComputedRef<string> = computed((): string => {
  const rating: number | null = props.assistant.business?.google_rating ?? null
  if (rating === null) return ''
  const score: string = rating.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  const reviewsCount: number | null = props.assistant.business?.google_reviews_count ?? null
  return reviewsCount
    ? `Noté ${score} sur 5 · ${reviewsCount.toLocaleString('fr-FR')} avis Google`
    : `Noté ${score} sur 5 sur Google`
})

const isOpenNow: ComputedRef<boolean | null> = computed(
  (): boolean | null => props.assistant.business?.is_open_now ?? null,
)

const openStatusLabel: ComputedRef<string> = computed((): string => {
  if (isOpenNow.value === null) return ''
  return isOpenNow.value
    ? 'Ouvert en ce moment.'
    : `Fermé en ce moment : ${assistantName.value} note votre demande, ${businessName.value} vous rappelle.`
})
</script>

<style scoped>
.business-page {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding-inline: 24px;
  padding-block: clamp(36px, 7vh, 80px) 40px;
  display: flex;
  flex-direction: column;
}
.business-page__header {
  display: grid;
  gap: 14px;
}
.business-page__trade {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ia-ink-dim);
}
.business-page__trade::before {
  content: '';
  width: 26px;
  height: 2px;
  background: var(--a-accent);
}
.business-page__name {
  margin: 0;
  font-family: var(--ia-font-display);
  font-weight: 600;
  font-size: clamp(32px, 5.6vw, 52px);
  line-height: 1.05;
  letter-spacing: -0.015em;
  text-wrap: balance;
}
.business-page__rating {
  margin: -4px 0 0;
  font-size: 13.5px;
  color: var(--ia-ink-dim);
  font-variant-numeric: tabular-nums;
}
.business-page__intro {
  margin: 0;
  max-width: 56ch;
  font-size: clamp(15px, 2.2vw, 17px);
  line-height: 1.6;
  color: var(--ia-ink-dim);
}
.business-page__status {
  margin: 0;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  max-width: 56ch;
  font-size: 14px;
  line-height: 1.5;
  color: var(--ia-ink);
}
.business-page__status-dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--ia-ink-dim);
}
.business-page__status--open .business-page__status-dot {
  background: #3fb950;
  box-shadow: 0 0 0 3px rgba(63, 185, 80, 0.2);
}
.business-page__layout {
  margin-top: clamp(26px, 4.5vh, 40px);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 28px;
}
@media (min-width: 900px) {
  .business-page__layout {
    grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
    gap: 36px;
    align-items: start;
  }
  .business-page__layout--single {
    grid-template-columns: minmax(0, 720px);
    justify-content: center;
  }
  .business-page__contact {
    position: sticky;
    top: 24px;
  }
}
.business-page__contact {
  display: grid;
  gap: 22px;
  padding: 22px 22px 18px;
  border: 1px solid var(--ia-line);
  border-radius: 18px;
  background: var(--ia-card);
}
.business-page__block {
  display: grid;
  gap: 8px;
}
.business-page__block-title {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ia-ink-dim);
}
.business-page__phone {
  margin: 0;
  justify-self: start;
  font-family: var(--ia-font-display);
  font-weight: 600;
  font-size: 24px;
  line-height: 1.2;
  color: var(--ia-ink);
  text-decoration: none;
  font-variant-numeric: tabular-nums;
}
.business-page__phone--link {
  text-decoration: underline;
  text-decoration-color: var(--a-accent);
  text-decoration-thickness: 2px;
  text-underline-offset: 5px;
}
.business-page__address {
  justify-self: start;
  font-size: 15px;
  line-height: 1.5;
  color: var(--ia-ink);
  text-decoration: underline;
  text-decoration-color: var(--ia-line);
  text-underline-offset: 3px;
}
.business-page__address:hover {
  text-decoration-color: var(--a-accent);
}
.business-page__footer {
  margin-top: clamp(32px, 6vh, 56px);
  padding-top: 18px;
  border-top: 1px solid var(--ia-line);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ia-ink-dim);
  text-align: center;
}
@media (max-width: 640px) {
  .business-page {
    padding-inline: 18px;
  }
}
</style>
