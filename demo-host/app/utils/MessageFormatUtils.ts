import type { AssistantMessageBlock, AssistantMessagePart } from '~/types/AssistantMessage'

// An http(s) address, up to the first space or closing quote; trailing punctuation is trimmed below.
const URL_PATTERN: RegExp = /https?:\/\/[^\s<>"«»*]+/g
const TRAILING_PUNCTUATION: RegExp = /[.,;:!?)\]}'’…]+$/
// Markdown bold (« **mot** »); a stray, unpaired mark is dropped.
const BOLD_PATTERN: RegExp = /\*\*(.+?)\*\*/g
const STRAY_BOLD_MARKS: RegExp = /\*\*/g
// A list item: « - », « • », « * » or « 1. » / « 1) » at the start of a line, then its text.
const LIST_ITEM: RegExp = /^\s*(?:[-•*]|\d{1,2}[.)])\s+(.*)$/
const ORDERED_ITEM: RegExp = /^\s*\d{1,2}[.)]\s+/

type OpenList = {
  ordered: boolean
  items: string[]
}

/**
 * Lays an assistant reply out without HTML: paragraphs split on blank lines, « - » lines as lists, bold words and
 * the site's addresses as links.
 */
export class MessageFormatUtils {
  /**
   * The blocks of a reply, in order.
   * @param message - The reply as the assistant wrote it (Markdown-light).
   * @returns Paragraphs and lists; a plain sentence is one paragraph.
   */
  static blocks(message: string): AssistantMessageBlock[] {
    const blocks: AssistantMessageBlock[] = []
    let paragraph: string[] = []
    let list: OpenList | null = null

    const closeParagraph: () => void = (): void => {
      if (paragraph.length > 0) blocks.push({ kind: 'paragraph', parts: MessageFormatUtils.lines(paragraph) })
      paragraph = []
    }
    const closeList: () => void = (): void => {
      if (list !== null) {
        blocks.push({
          kind: 'list',
          ordered: list.ordered,
          items: list.items.map((item: string): AssistantMessagePart[] => MessageFormatUtils.inline(item)),
        })
      }
      list = null
    }

    for (const rawLine of message.replace(/\r/g, '').split('\n')) {
      const line: string = rawLine.trimEnd()
      const item: RegExpExecArray | null = LIST_ITEM.exec(line)
      if (item !== null) {
        closeParagraph()
        const ordered: boolean = ORDERED_ITEM.test(line)
        if (list === null || list.ordered !== ordered) {
          closeList()
          list = { ordered, items: [] }
        }
        list.items.push(item[1] ?? '')
      } else if (line.trim() === '') {
        closeParagraph()
        closeList()
      } else {
        closeList()
        paragraph.push(line)
      }
    }
    closeParagraph()
    closeList()
    return blocks
  }

  /**
   * The inline parts of one line: plain text, bold words and links.
   * @param text - One line of the reply.
   * @returns The parts in order; a line without marks is one text part.
   */
  static inline(text: string): AssistantMessagePart[] {
    const parts: AssistantMessagePart[] = []
    let last: number = 0
    for (const match of text.matchAll(BOLD_PATTERN)) {
      const start: number = match.index ?? 0
      if (start > last) parts.push(...MessageFormatUtils.links(text.slice(last, start)))
      parts.push({ kind: 'bold', value: match[1] ?? '' })
      last = start + match[0].length
    }
    if (last < text.length) parts.push(...MessageFormatUtils.links(text.slice(last)))
    return parts
  }

  /**
   * The lines of a paragraph as inline parts, a line break between two lines.
   * @param lines - The paragraph's lines.
   * @returns The parts, with a break part between the lines.
   */
  private static lines(lines: string[]): AssistantMessagePart[] {
    return lines.flatMap((line: string, index: number): AssistantMessagePart[] =>
      index === 0
        ? MessageFormatUtils.inline(line)
        : [{ kind: 'break', value: '' }, ...MessageFormatUtils.inline(line)],
    )
  }

  /**
   * Plain text cut around the http(s) addresses it contains.
   * @param text - A piece of text without bold marks.
   * @returns Text and link parts in order.
   */
  private static links(text: string): AssistantMessagePart[] {
    const content: string = text.replace(STRAY_BOLD_MARKS, '')
    const parts: AssistantMessagePart[] = []
    let last: number = 0
    for (const match of content.matchAll(URL_PATTERN)) {
      const start: number = match.index ?? 0
      const url: string = match[0].replace(TRAILING_PUNCTUATION, '')
      if (start > last) parts.push({ kind: 'text', value: content.slice(last, start) })
      parts.push({ kind: 'link', value: url })
      last = start + url.length
    }
    if (last < content.length) parts.push({ kind: 'text', value: content.slice(last) })
    return parts
  }
}
