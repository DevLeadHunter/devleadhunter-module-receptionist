/**
 * Props of the casting grid: `demoUrl` names the demo host serving the portraits, `accentColor` tints the discs as the
 * widget will (the form's live value, so a new colour previews at once).
 */
export type AssistantPersonaPickerProps = {
  demoUrl: string
  accentColor: string | null
  customImageUrl: string | null
  customImageBackground: string | null
}

/** Events of the casting grid; `customize` asks for the business's own image to be sent or edited. */
export type AssistantPersonaPickerEmits = {
  customize: []
}
