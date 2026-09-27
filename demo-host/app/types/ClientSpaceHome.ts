import type { AiAssistantClientSpace } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'

/** One line of the home's « À faire » block. */
export type ClientSpaceHomeTask = {
  key: 'requests' | 'questions' | 'calendar'
  icon: 'phone' | 'help-circle' | 'calendar'
  tone: 'red' | 'accent' | 'amber'
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
