import type { H3Event } from 'h3'
import type { AiAssistantConfig, AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantLauncherConfig } from '~/types/AssistantLauncher'
import { LANGUAGE_LABELS, UI_LABELS } from '~/constants/AssistantWidgetLabels'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantAvatarUtils } from '~/utils/AssistantAvatarUtils'

/** The language of the launcher wording when the visitor's browser offers none of the assistant's. */
const DEFAULT_LANG: AssistantWidgetLang = 'fr'

/** How long the loader may keep a launcher configuration (a renamed persona shows within this delay). */
const CACHE_CONTROL: string = 'public, max-age=300, s-maxage=300'

/**
 * The language the launcher speaks: the first of the visitor's browser languages the assistant offers.
 * @param acceptLanguage - The `Accept-Language` header, if any.
 * @param configured - The assistant's language codes.
 * @returns An offered widget language, the assistant's first one, or French.
 */
function preferredLang(acceptLanguage: string | undefined, configured: string[]): AssistantWidgetLang {
  const offered: AssistantWidgetLang[] = configured.filter(
    (code: string): code is AssistantWidgetLang => code in LANGUAGE_LABELS,
  )
  const wanted: string[] = (acceptLanguage ?? '')
    .split(',')
    .map((part: string): string => part.trim().slice(0, 2).toLowerCase())
    .filter((code: string): boolean => code.length === 2)
  for (const code of wanted) {
    const match: AssistantWidgetLang | undefined = offered.find((offer: AssistantWidgetLang): boolean => offer === code)
    if (match) return match
  }
  return offered[0] ?? DEFAULT_LANG
}

/**
 * What the embed loader needs to draw a receptionist's launcher on a client's site, mounted at
 * `/embed-launcher/{slug}`: a few hundred bytes instead of the whole widget, cached briefly.
 * @param event - The incoming H3 request event.
 * @returns The launcher configuration; 404 when the assistant is unavailable.
 */
export default defineEventHandler(async (event: H3Event): Promise<AssistantLauncherConfig> => {
  const slug: string = getRouterParam(event, 'slug') ?? ''
  const apiBase: string = useRuntimeConfig(event).public.apiBase
  let config: AiAssistantConfig
  try {
    config = await $fetch<AiAssistantConfig>(`${apiBase}/api/v1/ai-assistants/public/${encodeURIComponent(slug)}`)
  } catch {
    throw createError({ statusCode: 404, statusMessage: 'Assistant unavailable' })
  }
  const lang: AssistantWidgetLang = preferredLang(getHeader(event, 'accept-language'), config.languages)
  const palette: AssistantAccentPalette = AssistantAccentUtils.palette(config.accent_color)
  setResponseHeader(event, 'Cache-Control', CACHE_CONTROL)
  return {
    assistant_name: config.assistant_name,
    portrait_path: AssistantAvatarUtils.portraitUrl(config.assistant_name, config.assistant_gender ?? null),
    accent_strong: palette.strong,
    accent_tint: palette.tint,
    say_before: UI_LABELS[lang].launcherBefore,
    say_after: UI_LABELS[lang].launcherAfter,
    open_label: UI_LABELS[lang].open.replace('{name}', config.assistant_name),
  }
})
