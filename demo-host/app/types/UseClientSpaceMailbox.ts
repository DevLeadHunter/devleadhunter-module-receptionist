import type { Ref } from 'vue'

export type UseClientSpaceMailboxReturn = {
  isMailboxBusy: Ref<boolean>
  mailboxError: Ref<string | null>
  connectMailbox: () => Promise<void>
  disconnectMailbox: () => Promise<void>
  clearMailboxFeedback: () => void
}
