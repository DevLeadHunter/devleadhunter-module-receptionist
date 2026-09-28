import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientSettings,
  AiAssistantClientSpace,
} from '~/types/AiAssistantClientSpace'
import { AssistantLanguageUtils } from '~/utils/AssistantLanguageUtils'

/**
 * Reads the receptionist's languages against the ones the client space offers, the legacy « lu » as « lb ».
 */
export class ClientSpaceLanguageUtils {
  /**
   * The offered language a served code stands for.
   * @param code - A language code, as the API served it.
   * @param options - The languages the client space offers.
   * @returns The offered option's code, or null when the widget does not speak it.
   */
  static offeredCode(code: string, options: AiAssistantClientLanguageOption[]): AssistantWidgetLanguage | null {
    const widgetCode: AssistantWidgetLanguage | null = AssistantLanguageUtils.fromStoredCode(code)
    const offered: AiAssistantClientLanguageOption | undefined = options.find(
      (option: AiAssistantClientLanguageOption): boolean => option.code === widgetCode,
    )
    return offered?.code ?? null
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
    const languages: AssistantWidgetLanguage[] = settings.languages
      .map((code: string): AssistantWidgetLanguage | null => ClientSpaceLanguageUtils.offeredCode(code, options))
      .filter((code: AssistantWidgetLanguage | null): code is AssistantWidgetLanguage => code !== null)
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
