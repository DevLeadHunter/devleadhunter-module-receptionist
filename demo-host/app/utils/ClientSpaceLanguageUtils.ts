import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientSettings,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'

/** Luxembourgish's code before it followed ISO 639-1; assistants saved earlier may still carry it. */
const LEGACY_LUXEMBOURGISH_CODE: string = 'lu'
const LUXEMBOURGISH_CODE: string = 'lb'

/**
 * Reads the receptionist's languages against the ones the client space offers, the legacy « lu » as « lb ».
 */
export class ClientSpaceLanguageUtils {
  /**
   * The offered language a served code stands for.
   * @param code - A language code, as the API served it.
   * @param options - The languages the client space offers.
   * @returns The offered option's code, or the served code when none matches.
   */
  static offeredCode(code: AssistantWidgetLang, options: AiAssistantClientLanguageOption[]): AssistantWidgetLang {
    const servedCode: string = code
    const currentCode: string = servedCode === LEGACY_LUXEMBOURGISH_CODE ? LUXEMBOURGISH_CODE : servedCode
    const option: AiAssistantClientLanguageOption | undefined =
      options.find((item: AiAssistantClientLanguageOption): boolean => item.code === currentCode) ??
      options.find((item: AiAssistantClientLanguageOption): boolean => item.code === servedCode)
    return option?.code ?? code
  }

  /**
   * Settings whose languages read as the offered ones, each once.
   * @param settings - The settings, as the API served them.
   * @param options - The languages the client space offers.
   * @returns The same settings with their languages matched to the offer.
   */
  static withOfferedLanguages(
    settings: AiAssistantClientSettings,
    options: AiAssistantClientLanguageOption[],
  ): AiAssistantClientSettings {
    const languages: AssistantWidgetLang[] = settings.languages.map((code: AssistantWidgetLang): AssistantWidgetLang =>
      ClientSpaceLanguageUtils.offeredCode(code, options),
    )
    return { ...settings, languages: [...new Set(languages)] }
  }

  /**
   * A space whose settings' languages read as the offered ones.
   * @param space - The space, as the API served it.
   * @returns The same space with its settings' languages matched to the offer.
   */
  static spaceWithOfferedLanguages(space: AiAssistantClientSpace): AiAssistantClientSpace {
    return { ...space, settings: ClientSpaceLanguageUtils.withOfferedLanguages(space.settings, space.language_options) }
  }
}
