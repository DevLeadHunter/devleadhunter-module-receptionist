export type AssistantChatCardTag = 'div' | 'form'

export type AssistantChatCardProps = {
  title: string
  note: string
  tag: AssistantChatCardTag
  primaryLabel: string
  primaryDisabled: boolean
  secondaryLabel: string
}

export type AssistantChatCardEmits = {
  primary: []
  secondary: []
}
