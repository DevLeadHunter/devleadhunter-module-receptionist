import type { Prospect } from '~/types'
import type { ProspectDrawerExtensionProps } from '~/types/ProspectDrawerExtension'

/** Props of the « Réceptionniste IA » block of the prospect drawer (the core hands them to every module block). */
export type AssistantProspectSectionProps = ProspectDrawerExtensionProps

/** Written out, not aliased to the core's `ProspectDrawerSectionEmits`: the SFC compiler resolves no `~/` here. */
export type AssistantProspectSectionEmits = {
  updated: [prospect: Prospect]
}
