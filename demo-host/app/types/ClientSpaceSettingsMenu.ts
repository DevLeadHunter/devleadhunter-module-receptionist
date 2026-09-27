import type { AiAssistantClientSpace } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'

/** One line of the settings menu: a label, a value at the right, and where it leads. */
export type ClientSpaceSettingsEntry = {
  key: string
  label: string
  value: string
  tone: 'plain' | 'amber' | 'green' | 'badge'
  screen: ClientSpaceSettingsScreen | 'agenda' | 'questions'
}

/** A group of the settings menu. */
export type ClientSpaceSettingsGroup = {
  title: string
  entries: ClientSpaceSettingsEntry[]
}

/** Props of the client-space settings menu. */
export type ClientSpaceSettingsMenuProps = {
  space: AiAssistantClientSpace
}

/** Events of the ClientSpaceSettingsMenu component. */
export type ClientSpaceSettingsMenuEmits = {
  open: [screen: ClientSpaceSettingsScreen]
  'open-agenda': []
  'open-questions': []
}
