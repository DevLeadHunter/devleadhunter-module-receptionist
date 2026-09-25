/** A piece of a line of an assistant reply: plain text, a bold word, an http(s) address shown as a link, or a line break. */
export type AssistantMessagePart = {
  kind: 'text' | 'bold' | 'link' | 'break'
  value: string
}

/** A paragraph of an assistant reply, its lines as inline parts. */
export type AssistantMessageParagraph = {
  kind: 'paragraph'
  parts: AssistantMessagePart[]
}

/** A list of an assistant reply (« - » lines, or numbered), each item as inline parts. */
export type AssistantMessageList = {
  kind: 'list'
  ordered: boolean
  items: AssistantMessagePart[][]
}

export type AssistantMessageBlock = AssistantMessageParagraph | AssistantMessageList
