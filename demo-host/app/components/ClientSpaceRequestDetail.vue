<template>
  <article class="cs-detail">
    <ClientSpaceBackBar v-if="props.showBack" back-label="Demandes" @back="emit('back')" />

    <div class="cs-detail__body">
      <div class="cs-head">
        <span class="cs-avatar cs-avatar--lg">{{ initials }}</span>
        <div class="cs-head__text">
          <h1 class="cs-head__name">{{ props.request.name }}</h1>
          <p class="cs-head__meta">
            <b :class="`cs-head__status--${status.tone}`">{{ status.label }}</b>
            · {{ props.request.received_label
            }}<template v-if="props.request.received_outside_hours"> · hors horaires</template
            ><template v-if="props.request.is_example"> · exemple</template>
          </p>
        </div>
      </div>

      <a v-if="contactHref" class="cs-contact" :href="contactHref">
        <ClientSpaceIcon :name="isPhone ? 'phone' : 'mail'" />
        <span class="cs-contact__value">{{ props.request.contact }}</span>
        <small>{{ isPhone ? 'appeler' : 'écrire' }}</small>
      </a>
      <p v-else class="cs-contact cs-contact--plain">
        <ClientSpaceIcon name="user" />
        <span class="cs-contact__value">{{ props.request.contact }}</span>
      </p>

      <p class="cs-sec">Message</p>
      <div class="cs-block">
        <p class="cs-text">{{ props.request.summary || 'Le visiteur n’a pas laissé de message.' }}</p>
      </div>

      <template v-if="isEmailRequest">
        <p class="cs-sec">Réponse préparée</p>
        <div class="cs-block">
          <p class="cs-text">
            Ce client vous a écrit par e-mail. Une réponse vous attend dans vos brouillons Gmail, dans sa conversation :
            relisez-la, puis envoyez-la.
          </p>
        </div>
      </template>

      <template v-if="eventRows.length > 0">
        <p class="cs-sec">Événement</p>
        <div class="cs-block">
          <p v-for="row in eventRows" :key="row.label" class="cs-cell cs-detail__event">
            <span class="cs-detail__event-label">{{ row.label }}</span>
            <b>{{ row.value }}</b>
          </p>
        </div>
      </template>

      <template v-if="props.request.appointment_booked">
        <p class="cs-sec">Rendez-vous</p>
        <div class="cs-block">
          <p class="cs-text">
            <b>{{ props.request.appointment_booked }}</b
            >, réservé dans votre agenda.
          </p>
        </div>
      </template>
      <template v-else-if="props.request.appointment_slots.length > 0">
        <p class="cs-sec">Créneaux souhaités</p>
        <div class="cs-block">
          <p v-for="slot in props.request.appointment_slots" :key="slot" class="cs-cell cs-detail__slot">
            <ClientSpaceIcon name="calendar" /><span>{{ slot }}</span>
          </p>
          <p class="cs-text cs-text--dim">À confirmer avec le visiteur, par téléphone ou par message.</p>
        </div>
      </template>

      <template v-if="props.request.photo_urls.length > 0">
        <p class="cs-sec">{{ photosLabel }}</p>
        <div class="cs-block cs-photos">
          <a
            v-for="(url, index) in props.request.photo_urls"
            :key="url"
            :href="url"
            target="_blank"
            rel="noopener noreferrer"
            referrerpolicy="no-referrer"
          >
            <img :src="url" :alt="`Photo ${index + 1}`" loading="lazy" referrerpolicy="no-referrer" />
          </a>
        </div>
      </template>

      <template v-if="conversationLines.length > 0">
        <p class="cs-sec">La conversation</p>
        <div class="cs-block cs-detail__conversation">
          <p
            v-for="(line, index) in conversationLines"
            :key="index"
            class="cs-detail__turn"
            :class="`cs-detail__turn--${line.role}`"
          >
            <img
              v-if="line.photo_url"
              class="cs-detail__turn-photo"
              :src="line.photo_url"
              alt="Photo envoyée par le visiteur"
              loading="lazy"
              referrerpolicy="no-referrer"
            />
            <span v-else class="cs-detail__bubble">{{ line.content }}</span>
          </p>
        </div>
      </template>

      <p v-if="props.errorMessage" class="cs-notice cs-notice--error cs-detail__error">{{ props.errorMessage }}</p>
    </div>

    <div v-if="!props.readOnly" class="cs-actions">
      <a
        v-if="isEmailRequest && props.gmailDraftsUrl"
        class="cs-btn cs-btn--primary"
        :href="props.gmailDraftsUrl"
        target="_blank"
        rel="noopener noreferrer"
      >
        <ClientSpaceIcon name="mail" />Ouvrir mes brouillons Gmail
      </a>
      <a v-else-if="contactHref" class="cs-btn cs-btn--primary" :href="contactHref">
        <ClientSpaceIcon :name="isPhone ? 'phone' : 'mail'" />{{ isPhone ? 'Appeler' : 'Écrire un e-mail' }}
      </a>
      <button
        v-if="isPending"
        type="button"
        class="cs-btn"
        :disabled="props.isBusy"
        @click="emit('handled', props.request.id)"
      >
        <ClientSpaceIcon name="check" />{{ props.isBusy ? 'Un instant…' : isPhone ? 'Rappelé' : 'Répondu' }}
      </button>
      <template v-else-if="props.request.status === 'handled'">
        <p v-if="props.request.outcome" class="cs-detail__done">
          {{ outcomeLabel }}
          <button
            type="button"
            class="cs-quiet cs-detail__change"
            :disabled="props.isBusy"
            @click="emit('outcome', props.request.id, null)"
          >
            Changer
          </button>
        </p>
        <template v-else>
          <p class="cs-detail__done">{{ doneLabel }} Et ensuite ?</p>
          <div class="cs-detail__outcome">
            <button
              type="button"
              class="cs-btn"
              :disabled="props.isBusy"
              @click="emit('outcome', props.request.id, 'won')"
            >
              <ClientSpaceIcon name="check" />Client gagné
            </button>
            <button
              type="button"
              class="cs-btn"
              :disabled="props.isBusy"
              @click="emit('outcome', props.request.id, 'lost')"
            >
              Pas donné suite
            </button>
          </div>
        </template>
      </template>
      <p v-else class="cs-detail__done">{{ doneLabel }}</p>
      <button
        v-if="isPending"
        type="button"
        class="cs-quiet"
        :disabled="props.isBusy"
        @click="emit('dropped', props.request.id)"
      >
        Ce n’est pas une vraie demande
      </button>
    </div>
  </article>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type {
  AiAssistantClientConversationLine,
  AiAssistantClientEvent,
  AiAssistantClientRequest,
} from '~/types/AiAssistantClientSpace'
import type {
  ClientSpaceRequestDetailEmits,
  ClientSpaceRequestDetailProps,
  ClientSpaceRequestEventRow,
} from '~/types/ClientSpaceRequestDetail'
import type { ClientSpaceRequestStatus } from '~/types/ClientSpaceRequestList'
import { ClientSpaceRequestUtils } from '~/utils/ClientSpaceRequestUtils'
import { ContactLinkUtils } from '~/utils/ContactLinkUtils'

/**
 * One request in full: the visitor, its contact as the first thing to tap, its message, its appointment or wished
 * half-days, its photos in full width. One main button (call, write, or open the Gmail drafts), « Rappelé » second,
 * and a quiet way to set a false request aside. Once called back, the business says what became of it: a client won,
 * or not.
 * @param request The request.
 * @param isBusy A call about this request is in flight.
 * @param errorMessage Why the last call was refused, if it was.
 * @param readOnly The example space: shown, never changed.
 * @param showBack On a phone, the detail replaces the list and shows a way back.
 * @param gmailDraftsUrl The Gmail drafts where the reply to an email request waits (null without a mailbox).
 */
const props: ClientSpaceRequestDetailProps = defineProps({
  request: { type: Object as PropType<AiAssistantClientRequest>, required: true },
  isBusy: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  readOnly: { type: Boolean, default: false },
  showBack: { type: Boolean, default: true },
  gmailDraftsUrl: { type: String as PropType<string | null>, default: null },
})

const emit: EmitFn<ClientSpaceRequestDetailEmits> = defineEmits<ClientSpaceRequestDetailEmits>()

const initials: ComputedRef<string> = computed((): string => ClientSpaceRequestUtils.initials(props.request.name))

const status: ComputedRef<ClientSpaceRequestStatus> = computed((): ClientSpaceRequestStatus =>
  ClientSpaceRequestUtils.status(props.request),
)

const isPending: ComputedRef<boolean> = computed((): boolean => props.request.status === 'new')

const isEmailRequest: ComputedRef<boolean> = computed((): boolean => props.request.channel === 'email')

const contactHref: ComputedRef<string | null> = computed((): string | null =>
  ContactLinkUtils.href(props.request.contact),
)

const isPhone: ComputedRef<boolean> = computed((): boolean => contactHref.value?.startsWith('tel:') === true)

const photosLabel: ComputedRef<string> = computed((): string =>
  props.request.photo_urls.length === 1 ? 'Photo' : `${props.request.photo_urls.length} photos`,
)

const conversationLines: ComputedRef<AiAssistantClientConversationLine[]> = computed(
  (): AiAssistantClientConversationLine[] => props.request.conversation ?? [],
)

/** The event's details as rows (date, place, guests, budget), only the ones the visitor gave. */
const eventRows: ComputedRef<ClientSpaceRequestEventRow[]> = computed((): ClientSpaceRequestEventRow[] => {
  const event: AiAssistantClientEvent | null = props.request.event
  if (!event) return []
  const rows: ClientSpaceRequestEventRow[] = []
  if (event.date) rows.push({ label: 'Date', value: event.date })
  if (event.place) rows.push({ label: 'Lieu', value: event.place })
  if (event.guests !== null) rows.push({ label: 'Invités', value: String(event.guests) })
  if (event.budget) rows.push({ label: 'Budget', value: event.budget })
  return rows
})

const doneLabel: ComputedRef<string> = computed((): string =>
  props.request.status === 'dropped' ? 'Mise de côté.' : isPhone.value ? 'Rappelé.' : 'Répondu.',
)

/** What became of the request, after the call back (« Rappelé. Client gagné. »). */
const outcomeLabel: ComputedRef<string> = computed(
  (): string => `${doneLabel.value} ${props.request.outcome === 'won' ? 'Client gagné.' : 'Pas donné suite.'}`,
)
</script>

<style scoped>
.cs-detail {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.cs-detail__body {
  flex: 1;
  padding-bottom: 16px;
}

.cs-detail__event {
  justify-content: space-between;
}

.cs-detail__event-label {
  color: var(--cs-dim);
}

.cs-detail__outcome {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.cs-detail__change {
  margin-left: 8px;
  padding: 0;
  font-size: 13px;
}

.cs-head__status--red {
  color: var(--cs-red);
}
.cs-head__status--accent {
  color: var(--cs-accent-text);
}
.cs-head__status--green {
  color: var(--cs-green);
}
.cs-head__status--grey {
  color: var(--cs-dim);
}
.cs-head__status--amber {
  color: var(--cs-amber);
}

.cs-detail__slot {
  margin: 0;
  font-weight: 500;
}

.cs-detail__slot :deep(.cs-icon) {
  color: var(--cs-accent-text);
}

.cs-detail__error {
  padding: 12px 16px 0;
}

.cs-detail__conversation {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
}

.cs-detail__turn {
  display: flex;
  margin: 0;
}

.cs-detail__turn--user {
  justify-content: flex-end;
}

.cs-detail__bubble {
  max-width: 85%;
  padding: 9px 12px;
  border-radius: 14px;
  font-size: 14.5px;
  line-height: 1.45;
  white-space: pre-line;
}

.cs-detail__turn--assistant .cs-detail__bubble {
  border: 1px solid var(--cs-line);
  border-bottom-left-radius: 4px;
  background: var(--cs-surface-2);
}

.cs-detail__turn--user .cs-detail__bubble {
  border-bottom-right-radius: 4px;
  background: var(--cs-accent-strong);
  color: var(--cs-on-accent);
}

.cs-detail__turn-photo {
  width: min(220px, 70%);
  border-radius: 12px;
  border: 1px solid var(--cs-line);
}

.cs-detail__done {
  margin: 0;
  padding: 6px 0;
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--cs-green);
}
</style>
