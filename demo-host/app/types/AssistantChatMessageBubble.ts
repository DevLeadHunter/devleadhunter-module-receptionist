import type { AssistantChatMessage } from './AiAssistant'

export type AssistantChatMessageBubbleProps = {
  message: AssistantChatMessage
  photoPreviewUrl: string | null
  avatarUrl: string | null
  avatarFallbackUrl: string
  assistantName: string
}
