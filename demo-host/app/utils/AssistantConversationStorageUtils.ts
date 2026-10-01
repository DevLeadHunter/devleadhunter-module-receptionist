import type { AssistantThreadMessage } from '~/types/AiAssistant'
import type { AssistantStoredConversation } from '~/types/AssistantThread'
import { AssistantThreadUtils } from '~/utils/AssistantThreadUtils'

/** Keeps a visitor's conversation in the browser's storage, so a returning visitor finds their thread. */
export class AssistantConversationStorageUtils {
  /**
   * The storage key of an assistant's conversation (the loader uses the same one on the host page).
   * @param slug - The assistant's public slug.
   * @returns The key.
   */
  static key(slug: string): string {
    return `dlh-assistant-${slug}`
  }

  /**
   * The serialised conversation kept under a key.
   * @param key - The storage key.
   * @returns The stored text, or null when there is none or storage is refused.
   */
  static read(key: string): string | null {
    // Inside the try: a browser that refuses storage to a third-party iframe throws on the mere access.
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  }

  /**
   * Keep a serialised conversation under a key.
   * @param key - The storage key.
   * @param raw - The serialised conversation.
   */
  static write(key: string, raw: string): void {
    try {
      localStorage.setItem(key, raw)
    } catch {
      // Storage unavailable (private mode, third-party iframe) or full: the widget keeps working from memory.
    }
  }

  /**
   * A conversation read back from its serialised form, each field checked.
   * @param raw - The serialised conversation, or null.
   * @returns The conversation, or null when there is none or it cannot be read.
   */
  static parse(raw: string | null): AssistantStoredConversation | null {
    if (!raw) return null
    try {
      const saved: unknown = JSON.parse(raw)
      if (typeof saved !== 'object' || saved === null) return null
      const fields: Record<string, unknown> = saved as Record<string, unknown>
      return {
        language: typeof fields.lang === 'string' ? fields.lang : null,
        sessionId: typeof fields.sessionId === 'string' && fields.sessionId ? fields.sessionId : null,
        messages: Array.isArray(fields.messages) ? fields.messages.filter(AssistantThreadUtils.isChatMessage) : [],
      }
    } catch {
      return null
    }
  }

  /**
   * A conversation in its serialised form, its most recent turns only, without the widget's own lines.
   * @param language - The widget's language.
   * @param sessionId - The visitor's session.
   * @param messages - The thread.
   * @returns The text to keep.
   */
  static serialize(language: string, sessionId: string, messages: AssistantThreadMessage[]): string {
    return JSON.stringify({
      // « lang »: the name the conversations already kept in visitors' browsers use.
      lang: language,
      sessionId,
      messages: AssistantThreadUtils.conversationTurns(messages),
    })
  }

  /**
   * The widget sessions this browser kept for an assistant: the one of its stored conversation, if any.
   * @param slug - The assistant's public slug.
   * @returns The session ids (none when the visitor never wrote, or storage is refused).
   */
  static sessionIds(slug: string): string[] {
    const stored: AssistantStoredConversation | null = AssistantConversationStorageUtils.parse(
      AssistantConversationStorageUtils.read(AssistantConversationStorageUtils.key(slug)),
    )
    return stored?.sessionId ? [stored.sessionId] : []
  }

  /**
   * A random id for a visitor's conversation (the browser's UUID when available).
   * @returns The new session id.
   */
  static newSessionId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
  }
}
