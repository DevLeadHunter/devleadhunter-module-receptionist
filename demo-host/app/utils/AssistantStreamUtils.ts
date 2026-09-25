import type { AssistantChatReply, AssistantChatStreamFrame } from '~/types/AiAssistant'

/** Reads the assistant's streamed reply (server-sent events) frame by frame. */
export class AssistantStreamUtils {
  /**
   * Read a streamed reply to its end, handing each piece of text over as it lands.
   * @param response - The streaming response (`text/event-stream`).
   * @param onDelta - Called with each piece of text as it arrives.
   * @returns The whole reply once the stream closes, or null when it closed without one.
   */
  static async read(response: Response, onDelta: (delta: string) => void): Promise<AssistantChatReply | null> {
    if (!response.body) return null
    const reader: ReadableStreamDefaultReader<Uint8Array> = response.body.getReader()
    const decoder: TextDecoder = new TextDecoder()
    let buffer: string = ''
    let closing: AssistantChatReply | null = null
    while (closing === null) {
      const chunk: ReadableStreamReadResult<Uint8Array> = await reader.read()
      if (chunk.done) break
      buffer += decoder.decode(chunk.value, { stream: true })
      const frames: string[] = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const parsed: AssistantChatStreamFrame | null = AssistantStreamUtils.parse(frame)
        if (!parsed) continue
        if (parsed.delta) onDelta(parsed.delta)
        if (parsed.done) closing = { reply: parsed.reply ?? '', offer_booking: parsed.offer_booking ?? false }
      }
    }
    return closing
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
