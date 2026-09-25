import type { ComputedRef, Ref } from 'vue'

/** `onOpenRequest` runs when the loader's own launcher on the host page asks the widget to open. */
export type UseAssistantWidgetFrameOptions = {
  inline: boolean
  isOpen: Ref<boolean>
  launcherElement: Ref<HTMLElement | null>
  onOpenRequest: () => void
}

/** `hostState` is the conversation the host page kept, null when it has none, undefined until the loader spoke. */
export type UseAssistantWidgetFrameReturn = {
  isEmbedded: Ref<boolean>
  isMobileLayout: ComputedRef<boolean>
  hostState: Ref<string | null | undefined>
}
