import type { ComputedRef, Ref } from 'vue'

/** `onOpenRequest` runs when the loader's own launcher on the host page asks the widget to open. */
export type UseAssistantWidgetFrameOptions = {
  inline: boolean
  isOpen: Ref<boolean>
  launcherElement: Ref<HTMLElement | null>
  onOpenRequest: () => void
}

export type UseAssistantWidgetFrameReturn = {
  isEmbedded: Ref<boolean>
  isMobileLayout: ComputedRef<boolean>
}
