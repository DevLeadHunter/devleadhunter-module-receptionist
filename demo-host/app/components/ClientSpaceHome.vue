<template>
  <div class="cs-home" data-capture="client-home">
    <section class="cs-kpis cs-home__kpis" aria-label="Chiffres clés">
      <component
        :is="kpi.opensRequests ? 'button' : 'div'"
        v-for="kpi in kpis"
        :key="kpi.key"
        :type="kpi.opensRequests ? 'button' : undefined"
        class="cs-kpi"
        :class="{ 'cs-kpi--link': kpi.opensRequests }"
        @click="kpi.opensRequests && emit('open-requests')"
      >
        <span class="cs-kpi__top">
          <span>{{ kpi.label }}</span>
          <span class="cs-kpi__icon" :class="{ 'cs-kpi__icon--red': kpi.tone === 'red' }">
            <ClientSpaceIcon :name="kpi.icon" />
          </span>
        </span>
        <span class="cs-kpi__value">{{ kpi.value }}</span>
        <span class="cs-kpi__hint">{{ kpi.hint }}</span>
      </component>
    </section>

    <section v-if="activityDays.length > 0" class="cs-panel cs-home__activity">
      <header class="cs-panel__head">
        <div>
          <h2 class="cs-panel__title">Activité de {{ props.space.assistant_name }}</h2>
          <p class="cs-panel__sub">Les {{ activityDays.length }} derniers jours, jour par jour</p>
        </div>
      </header>
      <ClientSpaceActivityChart :days="activityDays" />
    </section>

    <div class="cs-home__column cs-home__tasks">
      <section class="cs-panel cs-home__todo">
        <header class="cs-panel__head">
          <div>
            <h2 class="cs-panel__title">{{ isStarting ? 'Pour démarrer' : 'À faire' }}</h2>
            <p class="cs-panel__sub">{{ todoSubtitle }}</p>
          </div>
        </header>
        <div v-if="isStarting" class="cs-progress cs-home__progress">
          <span class="cs-progress__bar" :style="{ width: startProgressWidth }" />
        </div>
        <div v-for="task in tasks" :key="task.key" class="cs-todo">
          <span class="cs-todo__icon" :class="`cs-todo__icon--${task.tone}`"
            ><ClientSpaceIcon :name="task.icon"
          /></span>
          <span class="cs-todo__text">
            <b>{{ task.title }}</b>
            <span>{{ task.detail }}</span>
          </span>
          <button v-if="task.action" type="button" class="cs-btn cs-btn--small" @click="act(task)">
            {{ task.action }}
          </button>
        </div>
        <p v-if="tasks.length === 0" class="cs-panel__empty cs-home__clear">
          <span class="cs-todo__icon cs-todo__icon--green"><ClientSpaceIcon name="check" /></span>
          Rien à faire pour le moment. {{ props.space.assistant_name }} veille.
        </p>
      </section>

      <section v-if="props.space.calendar.status !== 'unavailable'" class="cs-panel cs-home__agenda">
        <header class="cs-panel__head">
          <div>
            <h2 class="cs-panel__title">Prochains rendez-vous</h2>
            <p class="cs-panel__sub">{{ agendaSubtitle }}</p>
          </div>
          <button type="button" class="cs-panel__link" @click="emit('open-agenda')">L’agenda</button>
        </header>
        <button
          v-for="appointment in nextAppointments"
          :key="appointment.id"
          type="button"
          class="cs-cell cs-home__appointment"
          @click="emit('open-agenda')"
        >
          <span class="cs-home__appointment-icon"><ClientSpaceIcon name="calendar-check" /></span>
          <span class="cs-home__appointment-text">
            <b>{{ appointment.start_label }}</b>
            <span>{{ appointment.type_label ? `${appointment.type_label} · ` : '' }}{{ appointment.name }}</span>
          </span>
        </button>
        <p v-if="nextAppointments.length === 0" class="cs-panel__empty">{{ agendaEmptyText }}</p>
      </section>
    </div>

    <section class="cs-panel cs-home__latest">
      <header class="cs-panel__head">
        <div>
          <h2 class="cs-panel__title">Dernières demandes</h2>
          <p class="cs-panel__sub">Les personnes qui ont laissé leurs coordonnées</p>
        </div>
        <button
          v-if="props.space.requests.length > 0"
          type="button"
          class="cs-panel__link"
          @click="emit('open-requests')"
        >
          Toutes les demandes
        </button>
      </header>
      <ClientSpaceRequestRow
        v-for="item in latest"
        :key="item.id"
        :request="item"
        data-capture="request-row"
        @select="emit('open-request', item.id)"
      />
      <div v-if="latest.length === 0" class="cs-home__first">
        <p class="cs-panel__empty">
          Personne n’a encore laissé ses coordonnées. Testez {{ props.space.assistant_name }} comme un client : ouvrez
          votre site, posez une question et laissez votre numéro. La demande apparaîtra ici, et vous recevrez le SMS.
        </p>
        <a v-if="props.space.website_url" class="cs-btn" :href="props.space.website_url" target="_blank" rel="noopener">
          <ClientSpaceIcon name="external-link" />Ouvrir votre site
        </a>
      </div>
    </section>

    <div class="cs-home__column cs-home__about">
      <section class="cs-panel cs-home__assistant">
        <ClientSpaceAssistantLine
          :name="`${props.space.assistant_name}, votre réceptionniste`"
          :portrait-url="props.portraitUrl"
          :portrait-fallback-url="props.portraitFallbackUrl"
          status-strong="En ligne"
          status-text="répond 24 h sur 24"
          @select="emit('open-settings-screen', 'assistant')"
        />
        <button
          v-for="link in assistantLinks"
          :key="link.screen"
          type="button"
          class="cs-cell cs-home__link"
          @click="emit('open-settings-screen', link.screen)"
        >
          <ClientSpaceIcon :name="link.icon" class="cs-home__link-icon" />
          <span>{{ link.label }}</span>
          <ClientSpaceIcon name="chevron-right" class="cs-home__link-chevron" />
        </button>
      </section>

      <section class="cs-panel cs-home__report">
        <header class="cs-panel__head">
          <div>
            <h2 class="cs-panel__title">
              {{ props.space.report ? `Rapport de ${props.space.report.month_label}` : 'Rapport du mois' }}
            </h2>
            <p class="cs-panel__sub">Envoyé aussi par e-mail, chaque début de mois</p>
          </div>
          <button
            v-if="props.space.report"
            type="button"
            class="cs-panel__link"
            @click="emit('open-settings-screen', 'report')"
          >
            Le lire
          </button>
        </header>
        <template v-if="props.space.report">
          <div class="cs-stats">
            <div v-for="figure in figures" :key="figure.label" class="cs-stat">
              <ClientSpaceIcon :name="figure.icon" />
              <span
                ><b>{{ figure.value }}</b
                ><span>{{ figure.label }}</span></span
              >
            </div>
          </div>
          <p v-if="props.space.report.won_line" class="cs-home__won">
            <ClientSpaceIcon name="check" />{{ props.space.report.won_line }}
          </p>
        </template>
        <p v-else class="cs-panel__empty">
          Le premier rapport de {{ props.space.assistant_name }} arrive au début du mois prochain, par e-mail et ici.
        </p>
      </section>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type {
  AiAssistantClientActivityDay,
  AiAssistantClientAppointment,
  AiAssistantClientGoogleProfile,
  AiAssistantClientInstalled,
  AiAssistantClientMailbox,
  AiAssistantClientRecentFigures,
  AiAssistantClientReport,
  AiAssistantClientRequest,
  AiAssistantClientSettings,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'
import type {
  ClientSpaceHomeAssistantLink,
  ClientSpaceHomeEmits,
  ClientSpaceHomeFigure,
  ClientSpaceHomeKpi,
  ClientSpaceHomeProps,
  ClientSpaceHomeTask,
} from '~/types/ClientSpaceHome'

/** How many requests the home lists before « Toutes les demandes ». */
const LATEST_COUNT: number = 5

/** How many upcoming appointments the home lists before « L’agenda ». */
const NEXT_APPOINTMENTS_COUNT: number = 3

/** The receptionist's settings the home leads to, beside her own screen. */
const ASSISTANT_LINKS: ClientSpaceHomeAssistantLink[] = [
  { screen: 'learned', icon: 'message-circle', label: 'Ce que vous lui avez appris' },
  { screen: 'limits', icon: 'ban', label: 'Prix, délais, garanties' },
  { screen: 'alerts', icon: 'bell', label: 'Vous prévenir' },
]

/**
 * The first screen of the client space, laid out like the business tools the client already uses: the key figures
 * of the last 30 days, the receptionist's activity day by day, what there is to do (or, before the first request,
 * the steps to start), the latest requests, the receptionist and her settings, the last monthly report. Every
 * panel leads somewhere.
 * @param space The whole space, as served by the API.
 * @param portraitUrl The receptionist's photo.
 * @param portraitFallbackUrl The bust drawn when the photo is missing.
 */
const props: ClientSpaceHomeProps = defineProps({
  space: { type: Object as PropType<AiAssistantClientSpace>, required: true },
  portraitUrl: { type: String, required: true },
  portraitFallbackUrl: { type: String, required: true },
})

const emit: EmitFn<ClientSpaceHomeEmits> = defineEmits<ClientSpaceHomeEmits>()

const assistantLinks: ClientSpaceHomeAssistantLink[] = ASSISTANT_LINKS

const pendingRequests: ComputedRef<AiAssistantClientRequest[]> = computed((): AiAssistantClientRequest[] =>
  props.space.requests.filter((item: AiAssistantClientRequest): boolean => item.status === 'new'),
)

const urgentPendingCount: ComputedRef<number> = computed(
  (): number =>
    pendingRequests.value.filter((item: AiAssistantClientRequest): boolean => item.type === 'urgent').length,
)

/** The days of the chart; none from an API that does not serve them yet. */
const activityDays: ComputedRef<AiAssistantClientActivityDay[]> = computed(
  (): AiAssistantClientActivityDay[] => props.space.activity ?? [],
)

/** Before the first request and the first report, the home walks the client through the start. */
const isStarting: ComputedRef<boolean> = computed(
  (): boolean => !props.space.is_example && props.space.requests.length === 0 && props.space.report === null,
)

/** The four tiles: who waits for a call back, then the last 30 days' requests, conversations and closed hours. */
const kpis: ComputedRef<ClientSpaceHomeKpi[]> = computed((): ClientSpaceHomeKpi[] => {
  const recent: AiAssistantClientRecentFigures | null = props.space.recent ?? null
  const pending: number = props.space.pending_count
  const urgent: number = urgentPendingCount.value
  const outsideHoursPct: number | null = recent?.outside_hours_pct ?? null
  const period: string = recent ? `en ${recent.days} jours` : ''
  let pendingHint: string = 'personne n’attend'
  if (urgent > 0) pendingHint = urgent === 1 ? 'dont 1 urgence' : `dont ${urgent} urgences`
  else if (pending > 0) pendingHint = pending === 1 ? 'attend votre appel' : 'attendent votre appel'
  return [
    {
      key: 'pending',
      label: 'À rappeler',
      value: String(pending),
      hint: pendingHint,
      icon: 'phone',
      tone: urgent > 0 ? 'red' : 'accent',
      opensRequests: true,
    },
    {
      key: 'requests',
      label: 'Demandes',
      value: recent ? String(recent.requests) : '—',
      hint: recent && recent.quotes > 0 ? `dont ${recent.quotes} devis, ${period}` : period,
      icon: 'inbox',
      tone: 'accent',
      opensRequests: true,
    },
    {
      key: 'conversations',
      label: 'Conversations',
      value: recent ? String(recent.conversations) : '—',
      hint: recent ? `visiteurs aidés ${period}` : '',
      icon: 'message-square',
      tone: 'accent',
      opensRequests: false,
    },
    {
      key: 'outside-hours',
      label: 'Hors horaires',
      value: outsideHoursPct === null ? '—' : `${outsideHoursPct} %`,
      hint: outsideHoursPct === null ? 'pas encore de demande' : 'des demandes, quand vous étiez fermé',
      icon: 'moon',
      tone: 'accent',
      opensRequests: false,
    },
  ]
})

/**
 * The steps to start: the SMS number, the address on the Google profile, the line on the site, the agenda. A
 * done step has no action.
 */
const steps: ComputedRef<ClientSpaceHomeTask[]> = computed((): ClientSpaceHomeTask[] => {
  const settings: AiAssistantClientSettings = props.space.settings
  const name: string = props.space.assistant_name
  const hasPhone: boolean = settings.alert_sms_enabled && Boolean(settings.alert_phone)
  const list: ClientSpaceHomeTask[] = [
    hasPhone
      ? {
          key: 'sms',
          icon: 'check',
          tone: 'green',
          title: 'Numéro pour les SMS',
          detail: settings.alert_phone ?? '',
          action: '',
        }
      : {
          key: 'sms',
          icon: 'message-square',
          tone: 'amber',
          title: 'Numéro pour les SMS',
          detail: 'pour être prévenu tout de suite',
          action: 'Ajouter',
        },
  ]
  const profile: AiAssistantClientGoogleProfile | null = props.space.google_profile
  if (profile) {
    list.push(
      profile.is_linked
        ? {
            key: 'google',
            icon: 'check',
            tone: 'green',
            title: 'Adresse sur votre fiche Google',
            detail: profile.linked_at_label ? `posée le ${profile.linked_at_label}` : 'posée',
            action: '',
          }
        : {
            key: 'google',
            icon: 'external-link',
            tone: 'amber',
            title: 'Adresse sur votre fiche Google',
            detail: 'les boutons Site web et Prendre rendez-vous',
            action: 'Voir',
          },
    )
  }
  const installed: AiAssistantClientInstalled | null = props.space.installed
  list.push(
    installed
      ? {
          key: 'install',
          icon: 'check',
          tone: 'green',
          title: `${name} sur votre site`,
          detail: `installée sur ${installed.host}`,
          action: '',
        }
      : {
          key: 'install',
          icon: 'code',
          tone: 'amber',
          title: `${name} sur votre site`,
          detail: 'une ligne à coller, ou à envoyer',
          action: 'Installer',
        },
  )
  if (props.space.calendar.status === 'connected') {
    list.push({ key: 'calendar', icon: 'check', tone: 'green', title: 'Agenda Google', detail: 'connecté', action: '' })
  } else if (props.space.calendar.status !== 'unavailable') {
    list.push({
      key: 'calendar',
      icon: 'calendar',
      tone: 'amber',
      title: 'Agenda Google',
      detail: 'pour y prendre les rendez-vous',
      action: props.space.calendar.status === 'error' ? 'Reconnecter' : 'Connecter',
    })
  }
  return list
})

/** What there is to do once the space lives: people to call back, questions, the agenda, the mailbox. */
const todos: ComputedRef<ClientSpaceHomeTask[]> = computed((): ClientSpaceHomeTask[] => {
  const list: ClientSpaceHomeTask[] = []
  const pending: number = props.space.pending_count
  if (pending > 0) {
    const urgent: number = urgentPendingCount.value
    list.push({
      key: 'requests',
      icon: 'phone',
      tone: urgent > 0 ? 'red' : 'accent',
      title: pending === 1 ? '1 personne à rappeler' : `${pending} personnes à rappeler`,
      detail: urgent > 0 ? (urgent === 1 ? 'dont 1 urgence' : `dont ${urgent} urgences`) : 'depuis votre site',
      action: 'Voir',
    })
  }
  const questions: number = props.space.unanswered.length
  if (questions > 0) {
    list.push({
      key: 'questions',
      icon: 'help-circle',
      tone: 'accent',
      title:
        questions === 1
          ? `1 question de ${props.space.assistant_name}`
          : `${questions} questions de ${props.space.assistant_name}`,
      detail: questions === 1 ? 'restée sans réponse' : 'restées sans réponse',
      action: 'Répondre',
    })
  }
  if (props.space.calendar.status === 'disconnected' || props.space.calendar.status === 'error') {
    list.push({
      key: 'calendar',
      icon: 'calendar',
      tone: 'amber',
      title: 'Agenda Google',
      detail: props.space.calendar.status === 'error' ? 'accès perdu, à reconnecter' : 'pas encore connecté',
      action: props.space.calendar.status === 'error' ? 'Reconnecter' : 'Connecter',
    })
  }
  const mailbox: AiAssistantClientMailbox | null = props.space.mailbox
  if (mailbox && mailbox.status !== 'connected') {
    list.push({
      key: 'mailbox',
      icon: 'mail',
      tone: 'amber',
      title: 'Votre boîte mail',
      detail: mailbox.status === 'error' ? 'accès perdu, à reconnecter' : 'pour préparer vos réponses aux e-mails',
      action: mailbox.status === 'error' ? 'Reconnecter' : 'Connecter',
    })
  }
  return list
})

const tasks: ComputedRef<ClientSpaceHomeTask[]> = computed((): ClientSpaceHomeTask[] =>
  isStarting.value ? steps.value : todos.value,
)

const doneStepCount: ComputedRef<number> = computed(
  (): number => steps.value.filter((step: ClientSpaceHomeTask): boolean => step.action === '').length,
)

/** The start's progress bar, in % of the steps done. */
const startProgressWidth: ComputedRef<string> = computed(
  (): string => `${Math.round((100 * doneStepCount.value) / Math.max(1, steps.value.length))}%`,
)

const todoSubtitle: ComputedRef<string> = computed((): string => {
  if (isStarting.value) return `${doneStepCount.value} sur ${steps.value.length} faits`
  if (tasks.value.length === 0) return 'Tout est à jour'
  return tasks.value.length === 1 ? '1 chose à faire' : `${tasks.value.length} choses à faire`
})

const figures: ComputedRef<ClientSpaceHomeFigure[]> = computed((): ClientSpaceHomeFigure[] => {
  const report: AiAssistantClientReport | null = props.space.report
  if (!report) return []
  const list: ClientSpaceHomeFigure[] = [
    { icon: 'message-square', value: String(report.conversations), label: 'conversations' },
    { icon: 'inbox', value: String(report.requests), label: report.requests > 1 ? 'demandes' : 'demande' },
    { icon: 'file-text', value: String(report.quotes), label: 'devis' },
  ]
  if (report.outside_hours_pct !== null) {
    list.push({ icon: 'moon', value: `${report.outside_hours_pct} %`, label: 'hors horaires' })
  }
  return list
})

const nextAppointments: ComputedRef<AiAssistantClientAppointment[]> = computed((): AiAssistantClientAppointment[] =>
  props.space.appointments.slice(0, NEXT_APPOINTMENTS_COUNT),
)

const agendaSubtitle: ComputedRef<string> = computed((): string =>
  props.space.calendar.status === 'connected'
    ? `Pris par ${props.space.assistant_name} dans votre agenda Google`
    : 'Agenda Google pas encore connecté',
)

const agendaEmptyText: ComputedRef<string> = computed((): string =>
  props.space.calendar.status === 'connected'
    ? 'Aucun rendez-vous à venir.'
    : `Connectez votre agenda Google : ${props.space.assistant_name} y pose les rendez-vous de vos clients.`,
)

/** The latest requests, the ones waiting first as the API orders them. */
const latest: ComputedRef<AiAssistantClientRequest[]> = computed((): AiAssistantClientRequest[] =>
  props.space.requests.slice(0, LATEST_COUNT),
)

/**
 * Open what a task is about.
 * @param task The task.
 */
function act(task: ClientSpaceHomeTask): void {
  if (task.key === 'requests') emit('open-requests')
  else if (task.key === 'questions') emit('open-question', 0)
  else if (task.key === 'sms') emit('open-settings-screen', 'alerts')
  else if (task.key === 'google') emit('open-settings-screen', 'google')
  else if (task.key === 'install') emit('open-settings-screen', 'install')
  else if (task.key === 'mailbox') emit('open-settings-screen', 'mailbox')
  else emit('open-agenda')
}
</script>

<style scoped>
.cs-home {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: 'kpis' 'tasks' 'latest' 'activity' 'about';
  align-content: start;
  gap: 12px;
  padding: 12px 16px 24px;
}

.cs-home__kpis {
  grid-area: kpis;
}

.cs-home__activity {
  display: flex;
  flex-direction: column;
  grid-area: activity;
}

/* Beside a taller column, the chart grows rather than leaving a blank under its axis. */
.cs-home__activity > .cs-chart {
  flex: 1;
}

.cs-home__tasks {
  grid-area: tasks;
}

.cs-home__latest {
  grid-area: latest;
  align-self: start;
}

.cs-home__about {
  grid-area: about;
  align-self: start;
}

.cs-home__column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

/* Beside the chart, the column's last panel takes the height left, so both columns end together. */
.cs-home__tasks > .cs-panel:last-child {
  flex: 1;
}

.cs-home__appointment {
  gap: 12px;
}

/* Outweighs the shared cell rule that stretches a cell's first span. */
.cs-home__appointment > .cs-home__appointment-icon {
  flex: none;
}

.cs-home__appointment-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--cs-accent-tint);
  color: var(--cs-accent-text);
}

.cs-home__appointment-icon .cs-icon {
  width: 17px;
  height: 17px;
}

.cs-home__appointment-text {
  display: grid;
  flex: 1;
  min-width: 0;
  line-height: 1.3;
}

.cs-home__appointment-text b {
  font-size: 14.5px;
  font-weight: 600;
}

.cs-home__appointment-text span {
  overflow: hidden;
  font-size: 13px;
  color: var(--cs-dim);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cs-home__progress {
  margin: 14px 16px 2px;
}

.cs-home__clear {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cs-home__first {
  display: grid;
  gap: 4px;
  padding-bottom: 16px;
}

.cs-home__first .cs-btn {
  margin: 0 16px;
}

/* The receptionist heads her panel: the panel draws the frame, not her line. */
.cs-home__assistant .cs-lea {
  margin: 0;
  border: 0;
  border-bottom: 1px solid var(--cs-line);
  border-radius: 0;
}

.cs-home__link {
  font-size: 14.5px;
}

.cs-home__link-icon {
  flex: none;
  width: 18px;
  height: 18px;
  color: var(--cs-faint);
}

.cs-home__link-chevron {
  flex: none;
  width: 16px;
  height: 16px;
  color: var(--cs-faint);
}

.cs-home__report .cs-stats {
  border-bottom: 1px solid var(--cs-line);
}

.cs-home__won {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 12px 16px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--cs-green);
}

.cs-home__won .cs-icon {
  flex: none;
  width: 16px;
  height: 16px;
}

@media (min-width: 1024px) {
  .cs-home {
    grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
    grid-template-areas:
      'kpis kpis'
      'activity tasks'
      'latest about';
    gap: 16px;
    max-width: 1240px;
    padding: 24px 28px 40px;
  }

  .cs-home__column {
    gap: 16px;
  }
}
</style>
