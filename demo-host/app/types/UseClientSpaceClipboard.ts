import type { Ref } from 'vue'

/** The texts the client space copies, each with its own « Copié » button. */
export type ClientSpaceCopyKey = 'link' | 'voicemail' | 'snippet'

export type UseClientSpaceClipboardReturn = {
  copiedKey: Ref<ClientSpaceCopyKey | null>
  copyText: (text: string, key: ClientSpaceCopyKey) => Promise<void>
}
