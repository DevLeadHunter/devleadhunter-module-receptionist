/** Where to paste the widget's script on one platform: its steps in order and a caveat, when there is one. */
export type AssistantInstallGuide = {
  key: string
  label: string
  steps: string[]
  note: string | null
}

/** Props of the install card: the script line the client pastes. */
export type AssistantInstallGuideCardProps = {
  embedSnippet: string
}
