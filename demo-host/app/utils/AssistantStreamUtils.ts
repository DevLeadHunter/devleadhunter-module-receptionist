import type { AssistantChatReply, AssistantChatRequestBody, AssistantChatStreamFrame } from '~/types/AiAssistant'
import type { AssistantStreamOutcome } from '~/types/AssistantRequest'
import {
  ASSISTANT_FIRST_BYTE_TIMEOUT_MS,
  ASSISTANT_REPLY_START_TIMEOUT_MS,
  ASSISTANT_STREAM_IDLE_TIMEOUT_MS,
} from '~/constants/AssistantWidgetLimits'
import { AssistantRequestUtils } from '~/utils/AssistantRequestUtils'

/** Asks for the assistant's reply as a stream (server-sent events) and reads it frame by frame, bounded in time. */
export class AssistantStreamUtils {
  /**
   * Ask for a reply as a stream, handing each piece of text over as it lands.
   * @param url - The streaming endpoint.
   * @param body - The chat request.
   * @param onDelta - Called with each piece of text as it arrives.
   * @returns The whole reply, a failure the plain request would meet too, or `fallback` when only the stream fails.
   */
  static async request(
    url: string,
    body: AssistantChatRequestBody,
    onDelta: (delta: string) => void,
  ): Promise<AssistantStreamOutcome> {
    const controller: AbortController = new AbortController()
    const headersTimer: ReturnType<typeof setTimeout> = setTimeout(
      (): void => controller.abort(),
      ASSISTANT_FIRST_BYTE_TIMEOUT_MS,
    )
    let response: Response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    } catch {
      return controller.signal.aborted ? { kind: 'failure', failure: 'network' } : { kind: 'fallback' }
    } finally {
      clearTimeout(headersTimer)
    }
    if (response.status === 404 || response.status === 429) {
      return { kind: 'failure', failure: AssistantRequestUtils.failureOfStatus(response.status) }
    }
    if (!response.ok || !response.body) return { kind: 'fallback' }
    try {
      const closing: AssistantChatReply | null = await AssistantStreamUtils.read(response.body, onDelta, controller)
      return closing ? { kind: 'reply', reply: closing } : { kind: 'fallback' }
    } catch {
      // Aborted by a timer: the server is too slow, the plain request would wait as long.
      return controller.signal.aborted ? { kind: 'failure', failure: 'network' } : { kind: 'fallback' }
    }
  }

  /**
   * Read a streamed reply to its end, aborting when its first words or its next piece take too long.
   * @param stream - The response body (`text/event-stream`).
   * @param onDelta - Called with each piece of text as it arrives.
   * @param controller - The request's controller, aborted by the timers.
   * @returns The whole reply once the stream closes, or null when it closed without one.
   * @throws The read error, an abort included.
   */
  private static async read(
    stream: ReadableStream<Uint8Array>,
    onDelta: (delta: string) => void,
    controller: AbortController,
  ): Promise<AssistantChatReply | null> {
    const reader: ReadableStreamDefaultReader<Uint8Array> = stream.getReader()
    const decoder: TextDecoder = new TextDecoder()
    let buffer: string = ''
    let closing: AssistantChatReply | null = null
    let silenceTimer: ReturnType<typeof setTimeout> = setTimeout(
      (): void => controller.abort(),
      ASSISTANT_REPLY_START_TIMEOUT_MS,
    )
    try {
      while (closing === null) {
        const chunk: ReadableStreamReadResult<Uint8Array> = await reader.read()
        clearTimeout(silenceTimer)
        if (chunk.done) break
        silenceTimer = setTimeout((): void => controller.abort(), ASSISTANT_STREAM_IDLE_TIMEOUT_MS)
        buffer += decoder.decode(chunk.value, { stream: true })
        const frames: string[] = buffer.split('\n\n')
        buffer = frames.pop() ?? ''
        for (const frame of frames) {
          const parsed: AssistantChatStreamFrame | null = AssistantStreamUtils.parse(frame)
          if (!parsed) continue
          if (parsed.delta) onDelta(parsed.delta)
          if (parsed.done) closing = AssistantStreamUtils.closingReply(parsed)
        }
      }
    } finally {
      clearTimeout(silenceTimer)
    }
    return closing
  }

  /**
   * The whole reply the closing frame carries (an older API leaves its later fields out).
   * @param frame - The closing frame.
   * @returns The reply.
   */
  private static closingReply(frame: AssistantChatStreamFrame): AssistantChatReply {
    return {
      reply: frame.reply ?? '',
      offer_booking: frame.offer_booking ?? false,
      follow_ups: frame.follow_ups ?? [],
      daily_limit_reached: frame.daily_limit_reached ?? false,
      captured_contact: frame.captured_contact ?? null,
    }
  }

  /**
   * One event of the stream, from its `data:` line.
   * @param frame - The raw event text.
   * @returns The frame, or null when it carries no JSON object.
   */
  private static parse(frame: string): AssistantChatStreamFrame | null {
    const line: string | undefined = frame.split('\n').find((part: string): boolean => part.startsWith('data:'))
    if (!line) return null
    try {
      const parsed: unknown = JSON.parse(line.slice('data:'.length).trim())
      return AssistantStreamUtils.isFrame(parsed) ? parsed : null
    } catch {
      return null
    }
  }

  /**
   * Whether a parsed value is a frame of the stream.
   * @param value - The parsed JSON.
   * @returns True for a plain object.
   */
  private static isFrame(value: unknown): value is AssistantChatStreamFrame {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
  }
}
