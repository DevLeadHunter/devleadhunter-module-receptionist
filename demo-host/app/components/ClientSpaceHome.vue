<template>
  <div class="cs-home" data-capture="client-home">
    <ClientSpaceAssistantLine
      :name="`${props.space.assistant_name}, votre réceptionniste`"
      :portrait-url="props.portraitUrl"
      :portrait-fallback-url="props.portraitFallbackUrl"
      status-strong="En ligne"
      status-text="répond à vos visiteurs, 24 h sur 24"
      @select="emit('open-settings-screen', 'assistant')"
    />

    <p class="cs-sec">
      {{ isStarting ? 'Pour démarrer' : 'À faire' }}
      <span v-if="isStarting" class="cs-sec__count">{{ doneStepCount }} / {{ tasks.length }}</span>
    </p>
    <div class="cs-block">
      <div v-for="task in tasks" :key="task.key" class="cs-todo">
        <span class="cs-todo__icon" :class="`cs-todo__icon--${task.tone}`"><ClientSpaceIcon :name="task.icon" /></span>
        <span class="cs-todo__text">
          <b>{{ task.title }}</b>
          <span>{{ task.detail }}</span>
        </span>
        <button v-if="task.action" type="button" class="cs-btn cs-btn--small" @click="act(task)">
          {{ task.action }}
        </button>
      </div>
      <p v-if="tasks.length === 0" class="cs-text cs-text--dim cs-home__clear">
        Rien à faire pour le moment. {{ props.space.assistant_name }} veille.
      </p>
    </div>

    <p class="cs-sec">
      {{ props.space.report ? props.space.report.month_label : 'Ce mois' }}
      <button
        v-if="props.space.report"
        type="button"
        class="cs-sec__link"
        @click="emit('open-settings-screen', 'report')"
      >
        Le rapport
      </button>
    </p>
    <div v-if="figures.length > 0" class="cs-block cs-stats">
      <div v-for="figure in figures" :key="figure.label" class="cs-stat">
        <ClientSpaceIcon :name="figure.icon" />
        <span
          ><b>{{ figure.value }}</b
          ><span>{{ figure.label }}</span></span
        >
      </div>
    </div>
    <div v-else class="cs-block">
      <p class="cs-text cs-text--dim">
        Le premier rapport de {{ props.space.assistant_name }} arrive au début du mois prochain, par email et ici.
      </p>
    </div>

    <p class="cs-sec cs-home__latest">
      Dernières demandes
      <button v-if="props.space.requests.length > 0" type="button" class="cs-sec__link" @click="emit('open-requests')">
        Toutes
      </button>
    </p>
    <div class="cs-block">
      <ClientSpaceRequestRow
        v-for="item in latest"
        :key="item.id"
        :request="item"
        data-capture="request-row"
        @select="emit('open-request', item.id)"
      />
      <p v-if="latest.length === 0" class="cs-text cs-text--dim">
        Personne n’a encore laissé ses coordonnées. Testez {{ props.space.assistant_name }} comme un client : ouvrez
        votre site, posez une question et laissez votre numéro. La demande apparaîtra ici, et vous recevrez le SMS.
      </p>
      <div v-if="latest.length === 0 && props.space.website_url" class="cs-home__open">
        <a class="cs-btn" :href="props.space.website_url" target="_blank" rel="noopener">
          <ClientSpaceIcon name="external-link" />Ouvrir votre site
        </a>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type {
  AiAssistantClientGoogleProfile,
  AiAssistantClientInstalled,
  AiAssistantClientMailbox,
  AiAssistantClientReport,
  AiAssistantClientRequest,
  AiAssistantClientSettings,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'
import type {
  ClientSpaceHomeEmits,
  ClientSpaceHomeFigure,
  ClientSpaceHomeProps,
  ClientSpaceHomeTask,
} from '~/types/ClientSpaceHome'

/** How many requests the home shows before « Toutes ». */
const LATEST_COUNT: number = 3

/**
 * The first screen of the client space: the receptionist and her status, what there is to do (or, before the
 * first request, the steps to start), the month's figures, the latest requests. Every block leads somewhere.
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

const pendingRequests: ComputedRef<AiAssistantClientRequest[]> = computed((): AiAssistantClientRequest[] =>
  props.space.requests.filter((item: AiAssistantClientRequest): boolean => item.status === 'new'),
)

/** Before the first request and the first report, the home walks the client through the start. */
const isStarting: ComputedRef<boolean> = computed(
  (): boolean => !props.space.is_example && props.space.requests.length === 0 && props.space.report === null,
)

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
    const urgent: number = pendingRequests.value.filter(
      (item: AiAssistantClientRequest): boolean => item.type === 'urgent',
    ).length
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
      detail: mailbox.status === 'error' ? 'accès perdu, à reconnecter' : 'pour préparer vos réponses aux emails',
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
  align-content: start;
}

.cs-home__clear {
  padding: 16px;
}

.cs-home__open {
  padding: 0 16px 16px;
}

.cs-home__open .cs-btn {
  width: 100%;
}
</style>
