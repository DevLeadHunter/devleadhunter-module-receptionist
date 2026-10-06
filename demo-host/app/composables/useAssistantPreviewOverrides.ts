import type { ComputedRef, Ref } from 'vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'

/** The identity edits the dashboard's atelier pushes into the demo page before they are saved. */
export type AssistantPreviewOverrides = {
  assistantName: string | null
  businessName: string | null
  accentColor: string | null
}

/** A hex colour, the only form the accent is accepted in. */
const HEX_COLOR_PATTERN: RegExp = /^#[0-9a-f]{6}$/i

/** Longest name accepted from a message, as the API bounds it. */
const NAME_MAX_LENGTH: number = 64

/**
 * A non-empty name from a message, bounded, or null.
 * @param value - The raw value of the message.
 * @returns The name, or null when the value is not a usable string.
 */
function sanitizeName(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed: string = value.trim().slice(0, NAME_MAX_LENGTH)
  return trimmed.length > 0 ? trimmed : null
}

/**
 * A hex colour from a message, or null.
 * @param value - The raw value of the message.
 * @returns The colour, or null when the value is not a hex colour.
 */
function sanitizeColor(value: unknown): string | null {
  return typeof value === 'string' && HEX_COLOR_PATTERN.test(value.trim()) ? value.trim() : null
}

/**
 * Listen, in live-edit mode only, for the `dlh:preview` messages carrying the receptionist's unsaved identity.
 * @param enabled - Whether live-edit mode is active (the `?_edit=1` query flag).
 * @returns The reactive overrides (all null until a first valid message arrives).
 */
export function useAssistantPreviewOverrides(enabled: ComputedRef<boolean>): {
  overrides: Ref<AssistantPreviewOverrides>
} {
  const overrides: Ref<AssistantPreviewOverrides> = ref({
    assistantName: null,
    businessName: null,
    accentColor: null,
  })

  /**
   * Apply one incoming `message` event when it carries a live-edit payload.
   * @param event - Raw message event from any parent window.
   */
  function onMessage(event: MessageEvent): void {
    if (!enabled.value) return
    const data: unknown = event.data
    if (typeof data !== 'object' || data === null) return
    const message: Record<string, unknown> = data as Record<string, unknown>
    if (message.type !== 'dlh:preview') return
    overrides.value = {
      assistantName: sanitizeName(message.assistant_name),
      businessName: sanitizeName(message.business_name),
      accentColor: sanitizeColor(message.accent_color),
    }
  }

  onMounted((): void => {
    window.addEventListener('message', onMessage)
  })

  onBeforeUnmount((): void => {
    window.removeEventListener('message', onMessage)
  })

  return { overrides }
}
