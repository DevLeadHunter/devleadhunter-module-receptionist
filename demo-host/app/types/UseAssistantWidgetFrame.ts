import type { ComputedRef, Ref } from 'vue'

/**
 * `launcherElement` reads the widget's own launcher (measured to size the frame); `onOpenRequest` runs when the
 * loader's launcher on the host page asks the widget to open, `instant` when the loader's placeholder sheet already
 * played the opening.
 */
export type UseAssistantWidgetFrameOptions = {
  inline: boolean
  launcherElement: () => HTMLElement | null
  onOpenRequest: (instant: boolean) => void
}

/**
 * `isFrameOpen` is what the loader frames at panel size (the panel open, or still closing); `hostState` is the
 * conversation the host page kept, null when it has none, undefined until the loader spoke.
 */
export type UseAssistantWidgetFrameReturn = {
  isEmbedded: Ref<boolean>
  isMobileLayout: ComputedRef<boolean>
  hostState: Ref<string | null | undefined>
  isPanelOpen: Ref<boolean>
  isPanelLeaving: Ref<boolean>
  isFrameOpen: ComputedRef<boolean>
}
