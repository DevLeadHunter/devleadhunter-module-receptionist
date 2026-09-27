<template>
  <div class="cs-home">
    <ClientSpaceAssistantLine
      :name="`${props.space.assistant_name}, votre réceptionniste`"
      :portrait-url="props.portraitUrl"
      :portrait-fallback-url="props.portraitFallbackUrl"
      status-strong="En ligne"
      status-text="répond à vos visiteurs, 24 h sur 24"
      @select="emit('open-settings-screen', 'assistant')"
    />

    <p class="cs-sec">À faire</p>
    <div class="cs-block">
      <div v-for="task in tasks" :key="task.key" class="cs-todo">
        <span class="cs-todo__icon" :class="`cs-todo__icon--${task.tone}`"><ClientSpaceIcon :name="task.icon" /></span>
        <span class="cs-todo__text">
          <b>{{ task.title }}</b>
          <span>{{ task.detail }}</span>
        </span>
        <button type="button" class="cs-btn cs-btn--small" @click="act(task)">{{ task.action }}</button>
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

    <p class="cs-sec">
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
        @select="emit('open-request', item.id)"
      />
      <p v-if="latest.length === 0" class="cs-text cs-text--dim">
        Personne n’a encore laissé ses coordonnées. Testez {{ props.space.assistant_name }} comme un client : ouvrez
        votre site, posez-lui une question et laissez votre numéro. La demande apparaîtra ici.
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type {
  AiAssistantClientReport,
  AiAssistantClientRequest,
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
 * The first screen of the client space: the receptionist and her status, what there is to do, the month's
 * figures, the latest requests. Every block leads somewhere.
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

const tasks: ComputedRef<ClientSpaceHomeTask[]> = computed((): ClientSpaceHomeTask[] => {
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
      detail: 'elle n’a pas su répondre',
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
  return list
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
  else emit('open-agenda')
}
</script>

<style scoped>
.cs-home {
  display: grid;
  align-content: start;
}

.cs-home__clear {
  padding: 16px;
}
</style>
