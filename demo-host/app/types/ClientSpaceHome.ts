import type { AiAssistantClientSpace } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'

/** One line of the home's « À faire » block, or one step of « Pour démarrer » (a done step has no action). */
export type ClientSpaceHomeTask = {
  key: 'requests' | 'questions' | 'calendar' | 'mailbox' | 'sms' | 'google' | 'install'
  icon: 'phone' | 'help-circle' | 'calendar' | 'mail' | 'check' | 'code' | 'message-square' | 'external-link'
  tone: 'red' | 'accent' | 'amber' | 'green'
  title: string
  detail: string
  action: string
}

/** One figure of the home's month block. */
export type ClientSpaceHomeFigure = {
  icon: 'message-square' | 'inbox' | 'file-text' | 'moon'
  value: string
  label: string
}

/** Props of the client-space home. */
export type ClientSpaceHomeProps = {
  space: AiAssistantClientSpace
  portraitUrl: string
  portraitFallbackUrl: string
}

/** Events of the ClientSpaceHome component. */
export type ClientSpaceHomeEmits = {
  'open-requests': []
  'open-agenda': []
  'open-request': [requestId: number]
  'open-question': [index: number]
  'open-settings-screen': [screen: ClientSpaceSettingsScreen]
}
