import type { AssistantChatReply } from '~/types/AiAssistant'

export type AssistantRequestFailure = 'rate-limited' | 'unavailable' | 'network' | 'server'

export type AssistantReplyOutcome =
  { kind: 'reply'; reply: AssistantChatReply } | { kind: 'failure'; failure: AssistantRequestFailure }

/** A streamed reply, or `fallback` when the stream cannot be used and the plain request must answer. */
export type AssistantStreamOutcome = AssistantReplyOutcome | { kind: 'fallback' }
