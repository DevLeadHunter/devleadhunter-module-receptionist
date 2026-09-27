/**
 * Desktop-first generation of an assistant's prospection video.
 *
 * Like the site video, the assistant video is built entirely on the user's machine — the sidecar
 * records the widget answering and montages it with its bundled ffmpeg, so the shared VPS is spared.
 * Unlike the site, there is **no Storyblok session** to reach, so a build never needs a login: it is
 * either produced locally or (off the desktop, or on a local failure) left to the server-side path.
 *
 * Every call is a no-op (`unavailable`) outside the desktop shell, so the web build falls back to the
 * VPS generation transparently.
 *
 * @module services/assistantSidecarService
 */
import { AiAssistantService } from '~/services/aiAssistantService'
import { DemoSiteService } from '~/services/demoSiteService'
import { ProfilePhotoService } from '~/services/profilePhotoService'
import { getScraperSidecarInfo } from '~/services/scraperSidecarService'
import type { SidecarBuildOutcome } from '~/services/sidecarVideoBuild'
import { pollAndFetchBuild, readSidecarError } from '~/services/sidecarVideoBuild'
import type { AiAssistantSummary } from '~/types/AiAssistant'

/** The presenter clip the assistant video uses (a speech about the assistant, not the site). */
const ASSISTANT_PRESENTER_MODULE: string = 'ai-assistant'

/**
 * Outcome of a full desktop assistant-video build.
 * - `done`: the whole video was rendered locally and stored.
 * - `unavailable`: not the desktop shell — the caller uses the server-side path.
 * - `failed`: something went wrong locally — the caller falls back to the server.
 */
export type AssistantVideoBuildStatus = 'done' | 'unavailable' | 'failed'

/** Result of a full desktop assistant-video build, with the updated assistant on success. */
export type AssistantVideoBuildResult = {
  status: AssistantVideoBuildStatus
  assistant?: AiAssistantSummary
  message?: string
}

/** Unsaved timings a calibration preview renders with, instead of the stored clip's. */
export type AssistantPreviewTimingOverrides = {
  presenter_intro: number
  presenter_outro: number
  total_seconds: number
}

/** Result of a calibration preview: the rendered mp4 when it worked, nothing published. */
export type AssistantPreviewVideoResult = {
  status: AssistantVideoBuildStatus
  video?: Blob
  message?: string
}

export class AssistantSidecarService {
  /**
   * Build the COMPLETE assistant video on the desktop (widget capture + montage), then upload it.
   *
   * Fetches the context + assistant presenter clip, has the sidecar render everything with its
   * bundled ffmpeg, then posts the finished video to the API — the VPS is never involved. Returns
   * `unavailable` off the desktop and `failed` (with a message) on any local error so the caller
   * can fall back to the server-side generation.
   * @param assistantId - The assistant to generate.
   * @returns The build outcome.
   */
  static async buildFullVideo(assistantId: number): Promise<AssistantVideoBuildResult> {
    const build: { status: AssistantVideoBuildStatus; blob?: Blob; message?: string } =
      await AssistantSidecarService.requestFullBuild(assistantId)
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
    const build: { status: AssistantVideoBuildStatus; blob?: Blob; message?: string } =
      await AssistantSidecarService.requestFullBuild(assistantId, { ...overrides, preview: true })
    if (build.status !== 'done' || !build.blob) {
      return { status: build.status, message: build.message }
    }
    return { status: 'done', video: build.blob }
  }

  /**
   * Run the sidecar's full desktop build (widget capture + montage) for an assistant.
   *
   * Shared by the real generation and the calibration preview. The build is DETACHED sidecar-side (a single
   * multi-minute response gets killed by the webview): start it, then follow it through the shared poll/fetch helper.
   * @param assistantId - The assistant to render.
   * @param payloadExtras - Fields merged over the API context (the preview's timings and flag).
   * @returns The produced zip blob (a bare mp4 for a preview), or the failure status.
   */
  private static async requestFullBuild(
    assistantId: number,
    payloadExtras: Record<string, unknown> = {},
  ): Promise<{ status: AssistantVideoBuildStatus; blob?: Blob; message?: string }> {
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
    // La photo est optionnelle : son absence (ou une erreur) ne bloque jamais le build.
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
    if (outcome.kind === 'timeout') return { status: 'failed', message: 'Génération trop longue — réessayez.' }
    return { status: 'failed', message: outcome.message }
  }
}
