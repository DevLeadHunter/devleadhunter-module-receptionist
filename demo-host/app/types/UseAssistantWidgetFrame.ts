import type { ComputedRef, Ref } from 'vue'

export type UseAssistantWidgetFrameOptions = {
  inline: boolean
  isOpen: Ref<boolean>
  launcherElement: Ref<HTMLElement | null>
}

export type UseAssistantWidgetFrameReturn = {
  isEmbedded: Ref<boolean>
  isMobileLayout: ComputedRef<boolean>
}
