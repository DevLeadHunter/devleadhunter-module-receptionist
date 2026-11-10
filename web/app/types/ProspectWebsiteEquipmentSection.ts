import type { Prospect } from '~/types'
import type { ProspectDrawerExtensionProps } from '~/types/ProspectDrawerExtension'

/** Props of the « Équipement du site » block of the prospect drawer (chat widget and contact form scan). */
export type ProspectWebsiteEquipmentSectionProps = ProspectDrawerExtensionProps

/** Written out, not aliased to the core's `ProspectDrawerSectionEmits`: the SFC compiler resolves no `~/` here. */
export type ProspectWebsiteEquipmentSectionEmits = {
  updated: [prospect: Prospect]
}
