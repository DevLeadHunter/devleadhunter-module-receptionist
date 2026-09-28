import type { AssistantChatMessage } from '~/types/AiAssistant'
import { ASSISTANT_STORED_MESSAGES_MAX } from '~/constants/AssistantWidgetLimits'

/** Reads and shapes the lines of a widget's thread: stored data checked, the turns the API receives. */
export class AssistantThreadUtils {
  /**
   * Whether a value is a well-formed chat message (guards against corrupted stored data).
   * @param value - A parsed entry from storage.
   * @returns True when it is a usable message.
   */
  static isChatMessage(value: unknown): value is AssistantChatMessage {
    if (typeof value !== 'object' || value === null) return false
    const entry: Record<string, unknown> = value as Record<string, unknown>
    const hasFollowUps: boolean =
      entry.follow_ups === undefined ||
      (Array.isArray(entry.follow_ups) &&
        entry.follow_ups.every((question: unknown): boolean => typeof question === 'string'))
    return (entry.role === 'user' || entry.role === 'assistant') && typeof entry.content === 'string' && hasFollowUps
  }

  /**
   * The recent turns as the API and the storage take them, each reply with the suggestions shown under it.
   * @param messages - The thread.
   * @returns The last turns, bounded, without any other field.
   */
  static conversationTurns(messages: AssistantChatMessage[]): AssistantChatMessage[] {
    return messages
      .slice(-ASSISTANT_STORED_MESSAGES_MAX)
      .map(({ role, content, follow_ups }: AssistantChatMessage): AssistantChatMessage =>
        follow_ups?.length ? { role, content, follow_ups } : { role, content },
      )
  }

  /**
   * A reply as a message of the thread, with the questions it offers next when there are any.
   * @param reply - The reply text.
   * @param followUps - The questions offered next (possibly missing from an older API).
   * @returns The message to push.
   */
  static replyMessage(reply: string, followUps: string[] | undefined): AssistantChatMessage {
    return followUps && followUps.length > 0
      ? { role: 'assistant', content: reply, follow_ups: followUps }
      : { role: 'assistant', content: reply }
  }
}
