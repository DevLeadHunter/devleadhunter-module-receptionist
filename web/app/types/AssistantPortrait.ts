/**
 * Props of the round portrait: `url` on the demo host, `name` for the initial shown when the photo is missing,
 * `accentColor` for the disc, `sizeClass` the Tailwind size and text size of the disc.
 */
export type AssistantPortraitProps = {
  url: string
  name: string
  accentColor: string | null
  sizeClass: string
}
