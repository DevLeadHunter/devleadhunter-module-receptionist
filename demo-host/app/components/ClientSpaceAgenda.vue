<template>
  <div class="cs-agenda">
    <div v-if="props.calendar.status === 'unavailable'" class="cs-block cs-agenda__connect">
      <span class="cs-todo__icon cs-todo__icon--accent"><ClientSpaceIcon name="calendar" /></span>
      <p class="cs-agenda__title">Vous confirmez vos rendez-vous</p>
      <p class="cs-text cs-text--dim">
        Vos rendez-vous arrivent en demandes, avec les créneaux souhaités par le visiteur : vous les confirmez
        vous-même, par téléphone ou par message.
      </p>
    </div>

    <div v-else-if="props.calendar.status !== 'connected'" class="cs-block cs-agenda__connect">
      <span class="cs-todo__icon cs-todo__icon--amber"><ClientSpaceIcon name="calendar" /></span>
      <p class="cs-agenda__title">
        {{
          props.calendar.status === 'error' ? 'L’accès à votre agenda a été perdu' : 'Google Agenda n’est pas connecté'
        }}
      </p>
      <p class="cs-text cs-text--dim">
        {{
          props.calendar.status === 'error'
            ? `Les rendez-vous repassent en demandes à confirmer. Reconnectez votre agenda pour que ${props.assistantName} réserve à nouveau.`
            : `${props.assistantName} note les créneaux souhaités mais ne peut pas réserver à votre place. Une fois connecté, ${props.assistantName} propose vos créneaux libres et réserve directement.`
        }}
      </p>
      <button
        v-if="!props.readOnly"
        type="button"
        class="cs-btn cs-btn--primary"
        :disabled="props.isBusy"
        @click="emit('connect')"
      >
        {{ props.calendar.status === 'error' ? 'Reconnecter Google Agenda' : 'Connecter Google Agenda' }}
      </button>
      <p v-if="!props.readOnly" class="cs-text cs-text--dim cs-agenda__hint">
        Google s’ouvre dans un nouvel onglet : autorisez l’accès à vos événements et à vos disponibilités, puis revenez
        ici.
      </p>
      <p v-if="props.errorMessage" class="cs-notice cs-notice--error">{{ props.errorMessage }}</p>
    </div>

    <template v-if="toConfirm.length > 0">
      <p class="cs-sec">À confirmer</p>
      <div class="cs-block">
        <ClientSpaceRequestRow
          v-for="item in toConfirm"
          :key="item.id"
          :request="item"
          @select="emit('open-request', item.id)"
        />
      </div>
    </template>

    <p class="cs-sec">Rendez-vous pris</p>
    <div class="cs-block">
      <div v-for="item in props.appointments" :key="item.id" class="cs-cell cs-agenda__appointment">
        <span class="cs-agenda__when">{{ item.start_label }}</span>
        <span class="cs-agenda__who">
          <b>{{ item.name }}</b>
          <span>{{ item.type_label ? `${item.type_label} · ` : '' }}{{ item.contact }}</span>
        </span>
      </div>
      <p v-if="props.appointments.length === 0" class="cs-text cs-text--dim">
        {{
          props.calendar.status === 'connected'
            ? `Aucun rendez-vous à venir. ${props.assistantName} les réserve dans votre agenda et ils apparaissent ici.`
            : 'Les rendez-vous réservés par votre réceptionniste apparaîtront ici une fois l’agenda connecté.'
        }}
      </p>
    </div>

    <template v-if="props.calendar.status === 'connected'">
      <p class="cs-sec">Réglages de l’agenda</p>
      <form class="cs-block cs-agenda__form" @submit.prevent="submit">
        <p class="cs-text cs-text--dim">
          Agenda Google connecté<template v-if="props.calendar.account_email">
            : <b>{{ props.calendar.account_email }}</b></template
          >. {{ props.assistantName }} y réserve les rendez-vous, sur vos créneaux libres et dans vos horaires.
        </p>
        <p v-if="props.calendar.last_error" class="cs-notice cs-notice--error cs-agenda__inset">
          Dernier problème le {{ props.calendar.last_error }}
        </p>

        <fieldset class="cs-agenda__fields" :disabled="props.readOnly">
          <label class="cs-field">
            <span class="cs-label">Durée d’un rendez-vous</span>
            <select v-model.number="duration" class="cs-input">
              <option v-for="minutes in props.calendar.duration_choices" :key="minutes" :value="minutes">
                {{ durationLabel(minutes) }}
              </option>
            </select>
          </label>
          <label class="cs-field">
            <span class="cs-label">Délai minimum avant un rendez-vous</span>
            <select v-model.number="notice" class="cs-input">
              <option v-for="hours in props.calendar.min_notice_choices" :key="hours" :value="hours">
                {{ hours === 0 ? 'Aucun' : `${hours} h` }}
              </option>
            </select>
          </label>
          <label class="cs-field">
            <span class="cs-label">Types de rendez-vous (facultatif, un par ligne)</span>
            <textarea
              v-model="typesText"
              class="cs-input cs-agenda__types"
              rows="3"
              placeholder="Révision&#10;Contrôle technique"
            />
            <span class="cs-hint">Le visiteur choisit l’un d’eux avant son créneau. {{ MAX_TYPES }} au plus.</span>
          </label>
          <label class="cs-field">
            <span class="cs-label">Agenda utilisé</span>
            <input
              v-model="calendarId"
              class="cs-input"
              type="text"
              maxlength="255"
              autocomplete="off"
              placeholder="Votre agenda principal"
            />
            <span class="cs-hint">
              Laissez vide pour votre agenda principal. Pour un autre agenda, collez son identifiant (paramètres de
              l’agenda, « Intégrer l’agenda »).
            </span>
          </label>
        </fieldset>

        <ClientSpaceSaveBar
          v-if="!props.readOnly"
          :is-busy="props.isBusy"
          :can-save="hasChanges"
          :error-message="props.errorMessage"
          :show-saved="props.hasSaved && !hasChanges"
        >
          <button type="button" class="cs-btn" :disabled="props.isBusy" @click="emit('disconnect')">Déconnecter</button>
        </ClientSpaceSaveBar>
        <p v-if="!props.readOnly" class="cs-hint cs-agenda__inset">
          Déconnecter efface l’accès gardé ici. Pour le retirer aussi chez Google : votre compte Google, rubrique
          Sécurité, accès des applications tierces.
        </p>
      </form>
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type {
  AiAssistantClientAppointment,
  AiAssistantClientCalendar,
  AiAssistantClientCalendarUpdate,
  AiAssistantClientRequest,
} from '~/types/AiAssistantClientSpace'
import type { ClientSpaceAgendaEmits, ClientSpaceAgendaProps } from '~/types/ClientSpaceAgenda'

const props: ClientSpaceAgendaProps = defineProps({
  calendar: { type: Object as PropType<AiAssistantClientCalendar>, required: true },
  appointments: { type: Array as PropType<AiAssistantClientAppointment[]>, required: true },
  requests: { type: Array as PropType<AiAssistantClientRequest[]>, required: true },
  assistantName: { type: String, required: true },
  isBusy: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  hasSaved: { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceAgendaEmits> = defineEmits<ClientSpaceAgendaEmits>()

/** How many appointment types a client may offer. */
const MAX_TYPES: number = 6

/** Google's id of the account's main agenda. */
const PRIMARY_CALENDAR_ID: string = 'primary'

const duration: Ref<number> = ref(props.calendar.duration_minutes)
const notice: Ref<number> = ref(props.calendar.min_notice_hours)
const typesText: Ref<string> = ref(props.calendar.appointment_types.join('\n'))
const calendarId: Ref<string> = ref(editableCalendarId(props.calendar.calendar_id))

/** The appointment requests still waiting, with wished half-days and no booking yet. */
const toConfirm: ComputedRef<AiAssistantClientRequest[]> = computed((): AiAssistantClientRequest[] =>
  props.requests.filter(
    (item: AiAssistantClientRequest): boolean =>
      item.status === 'new' && item.appointment_slots.length > 0 && !item.appointment_booked,
  ),
)

/** The kinds typed, one per line (or separated by commas), trimmed and bounded. */
const types: ComputedRef<string[]> = computed((): string[] =>
  typesText.value
    .split(/[\n,]/)
    .map((kind: string): string => kind.trim())
    .filter((kind: string): boolean => kind.length > 0)
    .slice(0, MAX_TYPES),
)

const changes: ComputedRef<AiAssistantClientCalendarUpdate> = computed((): AiAssistantClientCalendarUpdate => {
  const update: AiAssistantClientCalendarUpdate = {}
  if (duration.value !== props.calendar.duration_minutes) update.duration_minutes = duration.value
  if (notice.value !== props.calendar.min_notice_hours) update.min_notice_hours = notice.value
  if (types.value.join('\n') !== props.calendar.appointment_types.join('\n')) update.appointment_types = types.value
  const id: string = calendarId.value.trim() || PRIMARY_CALENDAR_ID
  if (id !== props.calendar.calendar_id) update.calendar_id = id
  return update
})

const hasChanges: ComputedRef<boolean> = computed((): boolean => Object.keys(changes.value).length > 0)

/**
 * A duration as the client reads it (« 45 min », « 1 h 30 »).
 * @param minutes The duration in minutes.
 * @returns Its label.
 */
function durationLabel(minutes: number): string {
  const hours: number = Math.floor(minutes / 60)
  const rest: number = minutes % 60
  if (hours === 0) return `${rest} min`
  return rest === 0 ? `${hours} h` : `${hours} h ${rest}`
}

/**
 * The agenda id as its field shows it: empty for the main agenda.
 * @param id - The agenda id the API keeps.
 * @returns The field's value.
 */
function editableCalendarId(id: string): string {
  return id === PRIMARY_CALENDAR_ID ? '' : id
}

/** Send only the settings that changed. */
function submit(): void {
  if (!hasChanges.value) return
  emit('save', changes.value)
}

watch(
  (): AiAssistantClientCalendar => props.calendar,
  (saved: AiAssistantClientCalendar): void => {
    duration.value = saved.duration_minutes
    notice.value = saved.min_notice_hours
    typesText.value = saved.appointment_types.join('\n')
    calendarId.value = editableCalendarId(saved.calendar_id)
  },
)
</script>

<style scoped>
.cs-agenda {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.cs-agenda__connect {
  display: grid;
  gap: 10px;
  justify-items: start;
  margin-top: 16px;
  padding: 18px 16px;
}

.cs-agenda__connect .cs-text {
  padding: 0;
}

.cs-agenda__connect .cs-btn {
  width: 100%;
  margin-top: 4px;
}

.cs-agenda__title {
  margin: 0;
  font-size: 16.5px;
  font-weight: 600;
}

.cs-agenda__hint {
  font-size: 13px;
}

.cs-agenda__appointment {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 2px 14px;
}

.cs-agenda__when {
  padding-top: 1px;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
  color: var(--cs-accent-text);
}

.cs-agenda__who {
  display: grid;
  min-width: 0;
  line-height: 1.35;
}

.cs-agenda__who b {
  font-weight: 600;
}

.cs-agenda__who span {
  font-size: 13.5px;
  color: var(--cs-dim);
}

.cs-agenda__form {
  display: grid;
  gap: 14px;
  padding-bottom: 16px;
}

.cs-agenda__form .cs-text {
  padding-bottom: 0;
}

.cs-agenda__inset {
  padding: 0 16px;
}

.cs-agenda__fields {
  display: grid;
  gap: 14px;
  margin: 0;
  padding: 0 16px;
  border: 0;
  min-width: 0;
}

.cs-agenda__types {
  resize: vertical;
  font: inherit;
}

.cs-agenda__form :deep(.cs-savebar) {
  padding: 0 16px;
}
</style>
