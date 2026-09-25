import type { AssistantChatMessage } from '~/types/AiAssistant'

export type AssistantChatMessageBubbleProps = {
  message: AssistantChatMessage
  photoPreviewUrl: string | null
  avatarUrl: string | null
  assistantName: string
}
