import type { AssistantWidgetLang } from '~/types/AiAssistant'

export type AssistantChatPhotoCardProps = {
  lang: AssistantWidgetLang
  isBusy: boolean
}

export type AssistantChatPhotoCardEmits = {
  pick: [file: File]
  cancel: []
}
