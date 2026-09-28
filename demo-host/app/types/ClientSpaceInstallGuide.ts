import type { AiAssistantClientInstalled } from '~/types/AiAssistantClientSpace'

export type ClientSpaceInstallGuideProps = {
  installed: AiAssistantClientInstalled | null
  embedSnippet: string | null
  websiteUrl: string | null
  assistantName: string
  businessName: string
}
