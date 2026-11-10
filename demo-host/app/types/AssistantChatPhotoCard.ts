import type { AssistantWidgetLanguage } from './AiAssistant'

export type AssistantChatPhotoCardProps = {
  language: AssistantWidgetLanguage
  isBusy: boolean
}

export type AssistantChatPhotoCardEmits = {
  pick: [file: File]
  cancel: []
}
