import type { AiAssistantSummary } from '~/types/AiAssistant'
import type {
  AssistantPreviewTimingOverrides,
  AssistantPreviewVideoResult,
  AssistantSidecarBuildResult,
  AssistantVideoBuildResult,
} from '~/types/AssistantSidecar'
import type { SidecarBuildOutcome } from '~/services/sidecarVideoBuild'
import { AiAssistantService } from '~/services/aiAssistantService'
import { DemoSiteService } from '~/services/demoSiteService'
import { ProfilePhotoService } from '~/services/profilePhotoService'
import { getScraperSidecarInfo } from '~/services/scraperSidecarService'
import { pollAndFetchBuild, readSidecarError } from '~/services/sidecarVideoBuild'

/** The presenter clip the assistant video uses (a speech about the assistant, not the site). */
const ASSISTANT_PRESENTER_MODULE: string = 'ai-assistant'

/** Builds a receptionist's prospecting video on the desktop app; off the desktop it answers `unavailable`. */
export class AssistantSidecarService {
  /**
   * Build the whole assistant video on the desktop (widget capture and montage), then upload it to the API.
   * @param assistantId - The assistant to generate.
   * @returns `done` with the updated assistant, `unavailable` off the desktop, `failed` with a message otherwise.
   */
  static async buildFullVideo(assistantId: number): Promise<AssistantVideoBuildResult> {
    const build: AssistantSidecarBuildResult = await AssistantSidecarService.requestFullBuild(assistantId)
    if (build.status !== 'done' || !build.blob) {
      return { status: build.status, message: build.message }
    }
    try {
      const assistant: AiAssistantSummary = await AiAssistantService.uploadFinalVideo(assistantId, build.blob)
      return { status: 'done', assistant }
    } catch (error) {
      return { status: 'failed', message: error instanceof Error ? error.message : 'Envoi de la vidéo échoué.' }
    }
  }

  /**
   * Render a calibration example of the receptionist video on the desktop, with unsaved timings; nothing is uploaded.
   * @param assistantId - The receptionist used as the example.
   * @param overrides - The intro, outro and middle lengths to try.
   * @returns The rendered mp4, or why it could not be made.
   */
  static async buildPreviewVideo(
    assistantId: number,
    overrides: AssistantPreviewTimingOverrides,
  ): Promise<AssistantPreviewVideoResult> {
    const build: AssistantSidecarBuildResult = await AssistantSidecarService.requestFullBuild(assistantId, {
      ...overrides,
      preview: true,
    })
    if (build.status !== 'done' || !build.blob) {
      return { status: build.status, message: build.message }
    }
    return { status: 'done', video: build.blob }
  }

  /**
   * Run the sidecar's full desktop build of an assistant, shared by the real generation and the calibration preview.
   * @param assistantId - The assistant to render.
   * @param payloadExtras - Fields merged over the API context (the preview's timings and flag).
   * @returns The produced zip (a bare mp4 for a preview), or the failure status.
   */
  private static async requestFullBuild(
    assistantId: number,
    payloadExtras: Record<string, unknown> = {},
  ): Promise<AssistantSidecarBuildResult> {
    const info: Awaited<ReturnType<typeof getScraperSidecarInfo>> = await getScraperSidecarInfo()
    if (!info) return { status: 'unavailable' }

    let context: Awaited<ReturnType<typeof AiAssistantService.getVideoContext>>
    let presenter: Blob
    try {
      context = await AiAssistantService.getVideoContext(assistantId)
      presenter = await DemoSiteService.fetchPresenterVideoFile(ASSISTANT_PRESENTER_MODULE)
    } catch (error) {
      return { status: 'failed', message: error instanceof Error ? error.message : 'Contexte vidéo indisponible.' }
    }
    // The photo is optional: a missing one (or an error) never stops the build.
    let presenterPhoto: Blob | null = null
    try {
      presenterPhoto = await ProfilePhotoService.fetchProfilePhotoBlob()
    } catch {
      presenterPhoto = null
    }

    const formData: FormData = new FormData()
    formData.append('payload', JSON.stringify({ ...context, ...payloadExtras }))
    formData.append('presenter', presenter, 'presenter.mp4')
    if (presenterPhoto) {
      formData.append('presenter_photo', presenterPhoto, 'presenter-photo.jpg')
    }

    // The build runs detached on the sidecar (the webview kills a response of several minutes): start it, then follow it.
    let startResponse: Response
    try {
      startResponse = await fetch(`http://127.0.0.1:${info.port}/video/build-assistant-full`, {
        method: 'POST',
        headers: { 'X-Sidecar-Token': info.token },
        body: formData,
      })
    } catch {
      return { status: 'failed', message: 'Le générateur local ne répond pas.' }
    }
    if (!startResponse.ok) {
      return { status: 'failed', message: await readSidecarError(startResponse) }
    }

    const outcome: SidecarBuildOutcome = await pollAndFetchBuild(info.port, info.token, context.slug, Date.now())
    if (outcome.kind === 'done') return { status: 'done', blob: outcome.blob }
    if (outcome.kind === 'timeout') return { status: 'failed', message: 'Génération trop longue, réessayez.' }
    return { status: 'failed', message: outcome.message }
  }
}
