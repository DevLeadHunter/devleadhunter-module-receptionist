/** The four sections of the client space. */
export type ClientSpaceSection = 'home' | 'requests' | 'agenda' | 'settings'

/** The screens of the settings section, each opened on top of the settings menu. */
export type ClientSpaceSettingsScreen =
  'assistant' | 'alerts' | 'learned' | 'report' | 'subscription' | 'limits' | 'google' | 'install' | 'help'

/**
 * Where the client space is: a section, and at most one thing opened on top of it (a request, one of the
 * receptionist's questions, or a settings screen).
 */
export type ClientSpaceLocation = {
  section: ClientSpaceSection
  requestId: number | null
  questionIndex: number | null
  settingsScreen: ClientSpaceSettingsScreen | null
}

/** One entry of the tab bar and the sidebar. */
export type ClientSpaceNavItem = {
  section: ClientSpaceSection
  label: string
  icon: 'house' | 'inbox' | 'calendar' | 'sliders-horizontal'
}
