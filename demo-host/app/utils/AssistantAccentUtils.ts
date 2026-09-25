/** A colour as red, green and blue components from 0 to 255. */
type RgbColor = { r: number; g: number; b: number }

/** The shades the widget derives from a business's accent. */
export type AssistantAccentPalette = {
  /** The accent itself: presence dots, rings, hairlines, never a fill under text. */
  accent: string
  /** The accent deepened until white reads on it: the one fill that carries text (visitor bubbles, buttons). */
  strong: string
  /** The accent deepened until it reads as text on the widget's paper: links, chip icons, selected pills. */
  text: string
  /** The accent washed towards white: the avatar's background and light bands. */
  tint: string
}

/** WCAG contrast a text colour must reach on its background (AA, normal text). */
const MIN_TEXT_CONTRAST: number = 4.5

/** The widget's light paper, on which the accent is also used as text. */
const PAPER: RgbColor = { r: 251, g: 249, b: 243 }

/** The white written on the strong shade. */
const ON_STRONG: RgbColor = { r: 255, g: 255, b: 255 }

/** How far the tint moves from the accent towards white (0 = the accent, 1 = white). */
const TINT_WASH: number = 0.72

/**
 * The accent colour of the assistant's widget and pages, and the shades that keep it readable whatever its hue.
 */
export class AssistantAccentUtils {
  /** The editorial gold used when the business has no accent colour of its own. */
  static readonly FALLBACK_ACCENT: string = '#a9793f'

  /**
   * The palette the widget paints with, from a business's accent (a hex colour; anything else falls back).
   * @param accent - The accent as stored, or null.
   * @returns The accent, its strong fill, its text shade and its tint.
   */
  static palette(accent: string | null | undefined): AssistantAccentPalette {
    const rgb: RgbColor | null = AssistantAccentUtils.parse(accent ?? '')
    if (!rgb) return AssistantAccentUtils.palette(AssistantAccentUtils.FALLBACK_ACCENT)
    return {
      accent: AssistantAccentUtils.format(rgb),
      strong: AssistantAccentUtils.format(AssistantAccentUtils.darkenUntilReadable(rgb, ON_STRONG)),
      text: AssistantAccentUtils.format(AssistantAccentUtils.darkenUntilReadable(rgb, PAPER)),
      tint: AssistantAccentUtils.format(AssistantAccentUtils.mixWithWhite(rgb, TINT_WASH)),
    }
  }

  /**
   * Parse a `#rgb` or `#rrggbb` colour.
   * @param value - The colour as typed.
   * @returns Its components, or null when it is not a hex colour.
   */
  private static parse(value: string): RgbColor | null {
    const hex: string = value.trim().replace(/^#/, '')
    const full: string = hex.length === 3 ? hex.replace(/(.)/g, '$1$1') : hex
    if (!/^[0-9a-f]{6}$/i.test(full)) return null
    return {
      r: parseInt(full.slice(0, 2), 16),
      g: parseInt(full.slice(2, 4), 16),
      b: parseInt(full.slice(4, 6), 16),
    }
  }

  /**
   * A colour as `#rrggbb`.
   * @param rgb - The components.
   * @returns The hex colour.
   */
  private static format(rgb: RgbColor): string {
    const part: (component: number) => string = (component: number): string =>
      Math.round(component).toString(16).padStart(2, '0')
    return `#${part(rgb.r)}${part(rgb.g)}${part(rgb.b)}`
  }

  /**
   * The relative luminance of a colour, as WCAG defines it.
   * @param rgb - The components.
   * @returns A value from 0 (black) to 1 (white).
   */
  private static luminance(rgb: RgbColor): number {
    const channel: (component: number) => number = (component: number): number => {
      const value: number = component / 255
      return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
    }
    return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b)
  }

  /**
   * The WCAG contrast ratio between two colours.
   * @param first - One colour.
   * @param second - The other.
   * @returns From 1 (identical) to 21 (black on white).
   */
  private static contrast(first: RgbColor, second: RgbColor): number {
    const lighter: number = Math.max(AssistantAccentUtils.luminance(first), AssistantAccentUtils.luminance(second))
    const darker: number = Math.min(AssistantAccentUtils.luminance(first), AssistantAccentUtils.luminance(second))
    return (lighter + 0.05) / (darker + 0.05)
  }

  /**
   * Darken a colour, a step at a time, until the given light colour reads on it (a dark accent is kept as is).
   * @param rgb - The accent.
   * @param against - The light colour that must read on the result: the paper, or the white of a button.
   * @returns The readable shade.
   */
  private static darkenUntilReadable(rgb: RgbColor, against: RgbColor): RgbColor {
    let shade: RgbColor = rgb
    for (let step: number = 0; step < 24 && AssistantAccentUtils.contrast(shade, against) < MIN_TEXT_CONTRAST; step++) {
      shade = { r: shade.r * 0.88, g: shade.g * 0.88, b: shade.b * 0.88 }
    }
    return shade
  }

  /**
   * Move a colour towards white.
   * @param rgb - The colour.
   * @param amount - How far to go, from 0 (unchanged) to 1 (white).
   * @returns The washed colour.
   */
  private static mixWithWhite(rgb: RgbColor, amount: number): RgbColor {
    return {
      r: rgb.r + (255 - rgb.r) * amount,
      g: rgb.g + (255 - rgb.g) * amount,
      b: rgb.b + (255 - rgb.b) * amount,
    }
  }
}
