import type { PresenterVideoTake } from '~/types/PresenterVideoTake'
import type { PresenterVideoTimelinePart } from '~/types/PresenterVideoTimingsCard'
import type { AssistantPreviewTimingOverrides } from '../types/AssistantSidecar'
import { PresenterVideoTimings } from '~/utils/presenterVideoTimings'

/** Mirror of the server's client-space chapter, which closes the receptionist's middle. */
export const RECEPTIONIST_SPACE_CHAPTER_SECONDS: number = 7

/** Mirror of the server's shortest chat scene: below it plus the chapter, the chapter is dropped. */
export const MIN_WIDGET_SCENE_SECONDS: number = 6

/** Where the receptionist video's parts fall, computed like the server does before a montage. */
export class AssistantVideoTimings {
  private constructor() {}

  /**
   * Timings a receptionist video build needs to be montaged with this take rather than the one in use.
   * @param take - The take montaged.
   * @returns The build's timing fields.
   */
  static buildTimings(take: PresenterVideoTake): AssistantPreviewTimingOverrides {
    return {
      presenter_duration: take.duration_seconds,
      presenter_intro: take.intro_seconds,
      presenter_outro: take.outro_seconds,
      total_seconds: PresenterVideoTimings.middleSeconds(take.duration_seconds, take.intro_seconds, take.outro_seconds),
    }
  }

  /**
   * Seconds of the receptionist's middle given to the client space, 0 when the chat would be left too short.
   * @param middleSeconds - The take's middle length.
   * @returns The chapter length.
   */
  static spaceChapterSeconds(middleSeconds: number): number {
    return middleSeconds >= MIN_WIDGET_SCENE_SECONDS + RECEPTIONIST_SPACE_CHAPTER_SECONDS
      ? RECEPTIONIST_SPACE_CHAPTER_SECONDS
      : 0
  }

  /**
   * The middle of the receptionist video: the chat answering, then the client space when there is room.
   * @param middleSeconds - The take's middle length.
   * @returns The chapters, without their widths.
   */
  static middleChapters(middleSeconds: number): PresenterVideoTimelinePart[] {
    const spaceSeconds: number = AssistantVideoTimings.spaceChapterSeconds(middleSeconds)
    const chat: PresenterVideoTimelinePart = {
      key: 'chat',
      label: 'Chat de la réceptionniste',
      shortLabel: 'Chat',
      seconds: middleSeconds - spaceSeconds,
      tone: 'bg-[var(--app-ink)] text-[var(--app-bg)]',
    }
    const space: PresenterVideoTimelinePart = {
      key: 'space',
      label: 'Espace client',
      shortLabel: 'Espace',
      seconds: spaceSeconds,
      tone: 'bg-[var(--app-ink-soft)] text-[var(--app-bg)]',
    }
    return spaceSeconds > 0 ? [chat, space] : [chat]
  }

  /**
   * The warning shown when the middle is too short to show the client space after the chat.
   * @param middleSeconds - The take's middle length.
   * @returns The warning, or null when the video shows both.
   */
  static shortMiddleWarning(middleSeconds: number): string | null {
    if (AssistantVideoTimings.spaceChapterSeconds(middleSeconds) > 0) {
      return null
    }
    return (
      `Moins de ${MIN_WIDGET_SCENE_SECONDS + RECEPTIONIST_SPACE_CHAPTER_SECONDS} s au milieu : la vidéo montrera le ` +
      "chat sans l'espace client. Allongez la prise du milieu pour le montrer."
    )
  }
}
