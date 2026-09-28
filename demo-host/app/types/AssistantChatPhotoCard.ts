import type { AssistantWidgetLanguage } from '~/types/AiAssistant'

export type AssistantChatPhotoCardProps = {
  language: AssistantWidgetLanguage
  isBusy: boolean
}

export type AssistantChatPhotoCardEmits = {
  pick: [file: File]
  cancel: []
}
