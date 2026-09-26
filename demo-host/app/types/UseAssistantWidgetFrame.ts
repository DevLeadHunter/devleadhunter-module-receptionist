import type { ComputedRef, Ref } from 'vue'

/**
 * `isOpen` is what the loader must frame at panel size (the panel open, or still closing); `onOpenRequest` runs
 * when the loader's own launcher on the host page asks the widget to open, `instant` when the loader's placeholder
 * sheet already played the opening.
 */
export type UseAssistantWidgetFrameOptions = {
  inline: boolean
  isOpen: Ref<boolean> | ComputedRef<boolean>
  launcherElement: Ref<HTMLElement | null>
  onOpenRequest: (instant: boolean) => void
}

/** `hostState` is the conversation the host page kept, null when it has none, undefined until the loader spoke. */
export type UseAssistantWidgetFrameReturn = {
  isEmbedded: Ref<boolean>
  isMobileLayout: ComputedRef<boolean>
  hostState: Ref<string | null | undefined>
}
