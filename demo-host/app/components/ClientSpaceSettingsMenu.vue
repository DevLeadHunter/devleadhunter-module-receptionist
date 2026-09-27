<template>
  <div class="cs-menu">
    <template v-for="group in groups" :key="group.title">
      <p class="cs-sec">{{ group.title }}</p>
      <div class="cs-block">
        <button v-for="entry in group.entries" :key="entry.key" type="button" class="cs-cell" @click="open(entry)">
          <span>{{ entry.label }}</span>
          <b v-if="entry.value" class="cs-cell__value" :class="`cs-cell__value--${entry.tone}`">{{ entry.value }}</b>
          <ClientSpaceIcon name="chevron-right" class="cs-cell__chevron" />
        </button>
      </div>
    </template>
    <p v-if="!props.space.is_example" class="cs-menu__foot">
      Lien personnel : il se prolonge à chaque ouverture (valable jusqu’au {{ props.space.link_expires_label }}). Ne le
      transférez pas : il donne accès à vos demandes.
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type {
  AiAssistantClientCalendar,
  AiAssistantClientLanguageOption,
  AiAssistantClientLimit,
  AiAssistantClientSettings,
  AiAssistantClientSpace,
  AiAssistantClientSubscription,
  AiAssistantClientSubscriptionStatus,
} from '~/types/AiAssistantClientSpace'
import type {
  ClientSpaceSettingsEntry,
  ClientSpaceSettingsGroup,
  ClientSpaceSettingsMenuEmits,
  ClientSpaceSettingsMenuProps,
} from '~/types/ClientSpaceSettingsMenu'

const SUBSCRIPTION_LABELS: Record<AiAssistantClientSubscriptionStatus, string> = {
  incomplete: 'En attente',
  active: 'Actif',
  past_due: 'Paiement en attente',
  canceled: 'Résilié',
}

/**
 * The settings as a menu of grouped lines, each leading to one screen: the receptionist, the alerts, the
 * connections, the monthly report, the subscription, the help. What remains to be done reads in amber.
 * @param space The whole space, as served by the API.
 */
const props: ClientSpaceSettingsMenuProps = defineProps({
  space: { type: Object as PropType<AiAssistantClientSpace>, required: true },
})

const emit: EmitFn<ClientSpaceSettingsMenuEmits> = defineEmits<ClientSpaceSettingsMenuEmits>()

/** The languages offered, as the client reads them (« Français, anglais »). */
const languagesLabel: ComputedRef<string> = computed((): string => {
  const labels: string[] = props.space.language_options
    .filter((option: AiAssistantClientLanguageOption): boolean => props.space.settings.languages.includes(option.code))
    .map((option: AiAssistantClientLanguageOption, index: number): string =>
      index === 0 ? option.label : option.label.toLowerCase(),
    )
  return labels.join(', ')
})

/** How many subjects the receptionist keeps a set answer on (« 6 sujets », « 4 sujets sur 6 »). */
const limitsLabel: ComputedRef<string> = computed((): string => {
  const total: number = props.space.limits.length
  const active: number = props.space.limits.filter((limit: AiAssistantClientLimit): boolean => limit.enabled).length
  if (total === 0) return ''
  return active === total ? `${total} sujets` : `${active} sujets sur ${total}`
})

const groups: ComputedRef<ClientSpaceSettingsGroup[]> = computed((): ClientSpaceSettingsGroup[] => {
  const settings: AiAssistantClientSettings = props.space.settings
  const calendar: AiAssistantClientCalendar = props.space.calendar
  const questions: number = props.space.unanswered.length
  const learned: number = props.space.faq.length
  const subscription: AiAssistantClientSubscription | null = props.space.subscription
  const list: ClientSpaceSettingsGroup[] = [
    {
      title: props.space.assistant_name,
      entries: [
        {
          key: 'name',
          label: 'Prénom affiché aux visiteurs',
          value: settings.assistant_name,
          tone: 'plain',
          screen: 'assistant',
        },
        { key: 'languages', label: 'Langues', value: languagesLabel.value, tone: 'plain', screen: 'assistant' },
        {
          key: 'questions',
          label: 'Ses questions',
          value: questions > 0 ? String(questions) : 'Aucune',
          tone: questions > 0 ? 'badge' : 'plain',
          screen: 'questions',
        },
        {
          key: 'learned',
          label: 'Ce que vous lui avez appris',
          value: learned === 1 ? '1 réponse' : `${learned} réponses`,
          tone: 'plain',
          screen: 'learned',
        },
        {
          key: 'limits',
          label: 'Prix, délais, garanties',
          value: limitsLabel.value,
          tone: 'plain',
          screen: 'limits',
        },
      ],
    },
    {
      title: 'Vous prévenir',
      entries: [
        {
          key: 'sms',
          label: 'SMS immédiat',
          value: settings.alert_sms_enabled ? settings.alert_phone || 'Numéro à saisir' : 'Non',
          tone: settings.alert_sms_enabled && !settings.alert_phone ? 'amber' : 'plain',
          screen: 'alerts',
        },
        {
          key: 'email',
          label: 'Email à chaque demande',
          value: settings.alert_email_enabled ? 'Oui' : 'Non',
          tone: 'plain',
          screen: 'alerts',
        },
        {
          key: 'quiet',
          label: 'Ne pas déranger',
          value:
            settings.alert_quiet_start_hour === settings.alert_quiet_end_hour
              ? 'Jamais'
              : `${settings.alert_quiet_start_hour} h à ${settings.alert_quiet_end_hour} h`,
          tone: 'plain',
          screen: 'alerts',
        },
      ],
    },
  ]
  const connections: ClientSpaceSettingsEntry[] = []
  if (props.space.google_profile) {
    connections.push({
      key: 'google',
      label: 'Votre fiche Google',
      value: props.space.google_profile.is_linked ? 'Adresse posée' : 'À poser',
      tone: props.space.google_profile.is_linked ? 'green' : 'amber',
      screen: 'google',
    })
  }
  connections.push({
    key: 'install',
    label: `${props.space.assistant_name} sur votre site`,
    value: props.space.installed ? `Installée sur ${props.space.installed.host}` : 'La ligne à coller',
    tone: props.space.installed ? 'green' : 'plain',
    screen: 'install',
  })
  if (calendar.status !== 'unavailable') {
    connections.push({
      key: 'calendar',
      label: 'Google Agenda',
      value:
        calendar.status === 'connected' ? 'Connecté' : calendar.status === 'error' ? 'À reconnecter' : 'À connecter',
      tone: calendar.status === 'connected' ? 'green' : 'amber',
      screen: 'agenda',
    })
  }
  list.push({ title: 'Connexions', entries: connections })
  if (props.space.report) {
    list.push({
      title: 'Chaque mois',
      entries: [
        {
          key: 'report',
          label: `Rapport de ${props.space.report.month_label.toLowerCase()}`,
          value: `${props.space.report.conversations} conversations`,
          tone: 'plain',
          screen: 'report',
        },
      ],
    })
  }
  list.push({
    title: 'Abonnement',
    entries: [
      {
        key: 'subscription',
        label: subscription ? subscription.price_label : 'Abonnement',
        value: subscription ? SUBSCRIPTION_LABELS[subscription.status] : 'Aucun',
        tone: subscription?.status === 'active' ? 'green' : subscription?.status === 'past_due' ? 'amber' : 'plain',
        screen: 'subscription',
      },
    ],
  })
  list.push({
    title: 'Aide',
    entries: [{ key: 'help', label: 'Une question ? On vous répond.', value: '', tone: 'plain', screen: 'help' }],
  })
  return list
})

/**
 * Open what a line is about.
 * @param entry The line.
 */
function open(entry: ClientSpaceSettingsEntry): void {
  if (entry.screen === 'agenda') emit('open-agenda')
  else if (entry.screen === 'questions') emit('open-questions')
  else emit('open', entry.screen)
}
</script>

<style scoped>
.cs-menu {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.cs-cell__chevron {
  color: var(--cs-faint);
}

.cs-menu__foot {
  margin: 0;
  padding: 18px 16px 20px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--cs-faint);
}
</style>
