import type { AssistantChatMessage } from '~/types/AiAssistant'

export type AssistantChatMessageBubbleProps = {
  message: AssistantChatMessage
  photoPreviewUrl: string | null
  avatarUrl: string | null
  avatarFallbackUrl: string
  assistantName: string
}
