/**
 * Props of the round portrait: `url` on the demo host or the business's own image, `name` for the initial shown when
 * the photo is missing, `accentColor` for the disc unless `background` sets its own colour, `sizeClass` the Tailwind
 * size and text size of the disc.
 */
export type AssistantPortraitProps = {
  url: string
  name: string
  accentColor: string | null
  background: string | null
  sizeClass: string
}
