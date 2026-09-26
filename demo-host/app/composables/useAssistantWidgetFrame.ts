import type { ComputedRef, Ref } from 'vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { UseAssistantWidgetFrameOptions, UseAssistantWidgetFrameReturn } from '~/types/UseAssistantWidgetFrame'

/** Below this host viewport width the panel goes full screen and the launcher drops its bubble. */
const MOBILE_MAX_WIDTH: number = 560

/** Below this host viewport height too (a phone held sideways): the panel would not fit beside the page. */
const MOBILE_MAX_HEIGHT: number = 640

/** Distance from the launcher to the viewport edge (mirrors the CSS) and room for its shadow. */
const LAUNCHER_EDGE_MARGIN: number = 22
const LAUNCHER_SHADOW_ALLOWANCE: number = 12

/**
 * Hand the visitor's conversation to the loader, which keeps it in the host page's own storage: Safari denies
 * storage to a third-party iframe, the host page's storage survives from page to page.
 * @param state - The serialised conversation.
 */
export function postHostPersist(state: string): void {
  if (typeof window === 'undefined' || window.parent === window) return
  window.parent.postMessage({ type: 'dlh-assistant-persist', state }, '*')
}

/**
 * The widget's dialogue with the loader framing it on a client's site: iframe size to give, host viewport to follow,
 * open requests from the loader's own launcher to honour.
 * @param options - Whether the widget is laid out in a page, its open state, its launcher element, what to do on open.
 * @returns Whether it runs in the loader's iframe, and whether the host screen calls for the mobile layout.
 */
export function useAssistantWidgetFrame(options: UseAssistantWidgetFrameOptions): UseAssistantWidgetFrameReturn {
  const isEmbedded: Ref<boolean> = ref(false)
  const hostState: Ref<string | null | undefined> = ref(undefined)
  const viewportWidth: Ref<number | null> = ref(null)
  const viewportHeight: Ref<number | null> = ref(null)
  let launcherObserver: ResizeObserver | null = null

  const isMobileLayout: ComputedRef<boolean> = computed(
    (): boolean =>
      (viewportWidth.value !== null && viewportWidth.value < MOBILE_MAX_WIDTH) ||
      (viewportHeight.value !== null && viewportHeight.value < MOBILE_MAX_HEIGHT),
  )

  /** Tell the loader how big the iframe must be: the launcher's footprint when closed, the panel when open. */
  function postFrameSize(): void {
    if (!isEmbedded.value) return
    const launcher: HTMLElement | null = options.launcherElement.value
    if (options.isOpen.value || !launcher) {
      window.parent.postMessage({ type: 'dlh-assistant-resize', open: options.isOpen.value }, '*')
      return
    }
    const footprint: DOMRect = launcher.getBoundingClientRect()
    window.parent.postMessage(
      {
        type: 'dlh-assistant-resize',
        open: false,
        width: footprint.width + LAUNCHER_EDGE_MARGIN + LAUNCHER_SHADOW_ALLOWANCE,
        height: footprint.height + LAUNCHER_EDGE_MARGIN + LAUNCHER_SHADOW_ALLOWANCE,
      },
      '*',
    )
  }

  /**
   * Read the host page's viewport posted by the loader; only the page that frames the widget may size it.
   * @param event - A message received from the parent window.
   */
  function onHostMessage(event: MessageEvent): void {
    if (event.source !== window.parent) return
    const data: Record<string, unknown> | null = typeof event.data === 'object' ? event.data : null
    if (!data) return
    if (data.type === 'dlh-assistant-open') {
      // `instant`: the loader's own sheet already played the opening, the panel shows at once in its place.
      options.onOpenRequest(data.instant === true)
      return
    }
    if (data.type === 'dlh-assistant-state') {
      hostState.value = typeof data.state === 'string' ? data.state : null
      return
    }
    if (data.type !== 'dlh-assistant-host' || typeof data.width !== 'number' || data.width <= 0) return
    viewportWidth.value = data.width
    viewportHeight.value = typeof data.height === 'number' && data.height > 0 ? data.height : null
  }

  /** Follow the page's own viewport when the widget floats on a page of ours rather than in an iframe. */
  function readOwnViewport(): void {
    viewportWidth.value = window.innerWidth
    viewportHeight.value = window.innerHeight
  }

  watch([options.isOpen, isMobileLayout], (): void => {
    nextTick(postFrameSize)
  })

  watch(options.launcherElement, (launcher: HTMLElement | null): void => {
    launcherObserver?.disconnect()
    if (launcher && launcherObserver) launcherObserver.observe(launcher)
  })

  onMounted((): void => {
    if (options.inline) return
    isEmbedded.value = window.parent !== window
    if (isEmbedded.value) {
      window.addEventListener('message', onHostMessage)
      if (typeof ResizeObserver !== 'undefined') {
        launcherObserver = new ResizeObserver((): void => postFrameSize())
        if (options.launcherElement.value) launcherObserver.observe(options.launcherElement.value)
      }
      window.parent.postMessage({ type: 'dlh-assistant-ready' }, '*')
      nextTick(postFrameSize)
      return
    }
    readOwnViewport()
    window.addEventListener('resize', readOwnViewport)
  })

  onBeforeUnmount((): void => {
    window.removeEventListener('message', onHostMessage)
    window.removeEventListener('resize', readOwnViewport)
    launcherObserver?.disconnect()
  })

  return { isEmbedded, isMobileLayout, hostState }
}
