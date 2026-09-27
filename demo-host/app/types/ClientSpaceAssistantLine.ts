/** Props of the receptionist's line: her portrait, her name and her status, as a button when it opens her settings. */
export type ClientSpaceAssistantLineProps = {
  name: string
  portraitUrl: string
  portraitFallbackUrl: string
  /** The status's first words, in green (« En ligne »). */
  statusStrong: string
  /** The rest of the status, in grey. */
  statusText: string
  /** The sidebar's smaller variant, without the chevron. */
  compact: boolean
}

/** Events of the ClientSpaceAssistantLine component. */
export type ClientSpaceAssistantLineEmits = {
  select: []
}
