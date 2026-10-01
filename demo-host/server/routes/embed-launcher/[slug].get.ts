import type { H3Event } from 'h3'
import type { AiAssistantConfig, AssistantWidgetLanguage } from '~/types/AiAssistant'
import type { AssistantLauncherConfig } from '~/types/AssistantLauncher'
import { UI_LABELS } from '~/constants/AssistantWidgetLabels'
import type { AssistantAccentPalette } from '~/utils/AssistantAccentUtils'
import { AssistantAccentUtils } from '~/utils/AssistantAccentUtils'
import { AssistantAvatarUtils } from '~/utils/AssistantAvatarUtils'
import { AssistantLanguageUtils } from '~/utils/AssistantLanguageUtils'

/** How long the loader may keep a launcher configuration (a renamed persona shows within this delay). */
const CACHE_CONTROL: string = 'public, max-age=300, s-maxage=300'

/**
 * The language the launcher speaks: the first of the visitor's browser languages the assistant offers.
 * @param acceptLanguage - The `Accept-Language` header, if any.
 * @param configured - The assistant's language codes.
 * @returns An offered widget language, the assistant's first one, or French.
 */
function launcherLanguage(acceptLanguage: string | undefined, configured: string[]): AssistantWidgetLanguage {
  const offered: AssistantWidgetLanguage[] = AssistantLanguageUtils.offered(configured)
  const wanted: string[] = (acceptLanguage ?? '').split(',')
  return AssistantLanguageUtils.firstOffered(wanted, offered) ?? offered[0] ?? AssistantLanguageUtils.DEFAULT_LANGUAGE
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
  let assistant: AiAssistantConfig
  try {
    assistant = await $fetch<AiAssistantConfig>(`${apiBase}/api/v1/ai-assistants/public/${encodeURIComponent(slug)}`)
  } catch {
    throw createError({ statusCode: 404, statusMessage: 'Assistant unavailable' })
  }
  const language: AssistantWidgetLanguage = launcherLanguage(getHeader(event, 'accept-language'), assistant.languages)
  const palette: AssistantAccentPalette = AssistantAccentUtils.palette(assistant.accent_color)
  setResponseHeader(event, 'Cache-Control', CACHE_CONTROL)
  return {
    assistant_name: assistant.assistant_name,
    portrait_path: AssistantAvatarUtils.portraitUrl(assistant.assistant_name, assistant.assistant_gender ?? null),
    portrait_url: assistant.avatar_url ?? null,
    portrait_background: assistant.avatar_background ?? null,
    accent_strong: palette.strong,
    accent_tint: palette.tint,
    say_before: UI_LABELS[language].launcherBefore,
    say_after: UI_LABELS[language].launcherAfter,
    open_label: UI_LABELS[language].open.replace('{name}', assistant.assistant_name),
  }
})
