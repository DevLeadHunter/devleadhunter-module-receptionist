import type { Ref } from 'vue'
import { ref } from 'vue'
import type { ClientSpaceCopyKey, UseClientSpaceClipboardReturn } from '~/types/UseClientSpaceClipboard'

/** How long a copy button says « Copié » after it copied. */
const COPIED_NOTICE_MS: number = 2500

/**
 * Copy buttons of the client space: the text goes to the clipboard, and the button that copied says so for a moment.
 * @returns Which button just copied, and the copy.
 */
export function useClientSpaceClipboard(): UseClientSpaceClipboardReturn {
  const copiedKey: Ref<ClientSpaceCopyKey | null> = ref(null)

  /**
   * Copy a text (the address, the voicemail, the line to paste); a browser that refuses gets it in a prompt.
   * @param text - What to copy.
   * @param key - Which button copied it.
   * @returns A promise resolved once the clipboard answered.
   */
  async function copyText(text: string, key: ClientSpaceCopyKey): Promise<void> {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      copiedKey.value = key
      window.setTimeout((): void => {
        if (copiedKey.value === key) copiedKey.value = null
      }, COPIED_NOTICE_MS)
    } catch {
      window.prompt('Copiez ce texte :', text)
    }
  }

  return { copiedKey, copyText }
}
