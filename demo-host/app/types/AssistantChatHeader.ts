export type AssistantChatHeaderProps = {
  assistantName: string
  businessName: string
  roleLabel: string
  onlineLabel: string
  avatarUrl: string
  avatarFallbackUrl: string
  canClose: boolean
}

export type AssistantChatHeaderEmits = {
  close: []
}
