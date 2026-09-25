/**
 * Props of the casting grid: `demoUrl` names the demo host serving the portraits, `accentColor` tints the discs as the
 * widget will (the form's live value, so a new colour previews at once).
 */
export type AssistantPersonaPickerProps = {
  demoUrl: string
  accentColor: string | null
}
