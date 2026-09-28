/** What the keyboard can reach with Tab, when enabled. */
const TABBABLE_SELECTOR: string = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/** Keeps the keyboard inside a modal dialog: Tab from its last control comes back to its first, and the reverse. */
export class FocusTrapUtils {
  /**
   * The controls of a container the keyboard reaches, in document order, the hidden ones left out.
   * @param container - The dialog.
   * @returns Its tabbable elements.
   */
  static tabbableElements(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll<HTMLElement>(TABBABLE_SELECTOR)).filter(
      (element: HTMLElement): boolean => element.getClientRects().length > 0,
    )
  }

  /**
   * Wrap a Tab key press around the container's controls instead of letting the focus leave it.
   * @param event - The Tab key press.
   * @param container - The dialog.
   */
  static keepTabInside(event: KeyboardEvent, container: HTMLElement): void {
    const tabbables: HTMLElement[] = FocusTrapUtils.tabbableElements(container)
    const first: HTMLElement | undefined = tabbables[0]
    const last: HTMLElement | undefined = tabbables[tabbables.length - 1]
    if (!first || !last) {
      event.preventDefault()
      return
    }
    const active: Element | null = document.activeElement
    const isInside: boolean = active !== null && container.contains(active)
    if (event.shiftKey && (active === first || !isInside)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && (active === last || !isInside)) {
      event.preventDefault()
      first.focus()
    }
  }
}
