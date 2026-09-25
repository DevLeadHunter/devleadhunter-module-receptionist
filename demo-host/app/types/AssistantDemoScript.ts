import type { AssistantChatMessage } from '~/types/AiAssistant'

/** One turn of the conversation the demo page plays by itself, before handing over to the visitor. */
export type AssistantDemoScriptStep = AssistantChatMessage

/** How the demo page reads the page it is on, to open with the right first sentence. */
export type AssistantGreetingContext = 'default' | 'contact' | 'quote' | 'appointment'

/** The host page of an embedded widget, as the loader reports it. */
export type AssistantHostPage = {
  path: string
  title: string
}
