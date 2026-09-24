/** A piece of an assistant reply: plain text, or an http(s) address shown as a link. */
export type AssistantMessagePart = {
  kind: 'text' | 'link'
  value: string
}
