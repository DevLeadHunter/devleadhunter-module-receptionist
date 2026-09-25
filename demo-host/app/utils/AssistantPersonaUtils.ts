import type { AiAssistantPersonaGender } from '~/types/AiAssistant'

/** French wording that agrees with the assistant persona's gender, as resolved by the API from its first name. */
export class AssistantPersonaUtils {
  /**
   * Subject pronoun for the persona, lowercase ("il" / "elle").
   * @param gender - The persona gender from the public config; feminine when absent.
   * @returns 'il' for a masculine persona, 'elle' otherwise.
   */
  static subjectPronoun(gender: AiAssistantPersonaGender | undefined): string {
    return gender === 'masculine' ? 'il' : 'elle'
  }

  /**
   * Subject pronoun for the persona at the start of a sentence ("Il" / "Elle").
   * @param gender - The persona gender from the public config; feminine when absent.
   * @returns 'Il' for a masculine persona, 'Elle' otherwise.
   */
  static capitalizedSubjectPronoun(gender: AiAssistantPersonaGender | undefined): string {
    return gender === 'masculine' ? 'Il' : 'Elle'
  }
}
