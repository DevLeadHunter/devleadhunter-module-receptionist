/**
 * What the embed loader needs to draw the launcher on a client's site before the widget loads: the name, the
 * portrait path on this host, the two accent shades of the ring and the disc, and the wording in the visitor's
 * language (`say_before` + name + `say_after`).
 */
export type AssistantLauncherConfig = {
  assistant_name: string
  portrait_path: string
  accent_strong: string
  accent_tint: string
  say_before: string
  say_after: string
  open_label: string
}
