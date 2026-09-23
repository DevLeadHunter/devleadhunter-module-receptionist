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
import type { VideoBuildProgress } from '~/services/storyblokSidecarService'
import type { AiAssistantSummary } from '~/types/AiAssistant'

/** The presenter clip the assistant video uses (a speech about the assistant, not the site). */
const ASSISTANT_PRESENTER_MODULE: string = 'ai-assistant'

/** Ceiling for a detached local build — capture + montage can take several minutes. */
const BUILD_WAIT_LIMIT_MS: number = 20 * 60 * 1000

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
   * Run the sidecar's full desktop build (widget capture + montage) for an assistant.
   *
   * The build is DETACHED sidecar-side (a single multi-minute response gets killed by the webview):
   * start it, poll its progress, then fetch the produced file.
   * @param assistantId - The assistant to render.
   * @returns The produced zip blob, or the failure status.
   */
  private static async requestFullBuild(
    assistantId: number,
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
    formData.append('payload', JSON.stringify(context))
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
      return { status: 'failed', message: await AssistantSidecarService.readSidecarError(startResponse) }
    }

    // The build runs detached — follow it through the progress endpoint, then fetch the result.
    const startedAtMs: number = Date.now()
    const deadlineMs: number = startedAtMs + BUILD_WAIT_LIMIT_MS
    while (Date.now() < deadlineMs) {
      await new Promise<void>((resolve: () => void): void => {
        window.setTimeout(resolve, 2000)
      })
      const progress: VideoBuildProgress | null = await AssistantSidecarService.getBuildProgress(info, context.slug)
      if (!progress || progress.updatedAt * 1000 < startedAtMs - 2000) continue
      if (progress.step === 'error') {
        return { status: 'failed', message: progress.message || 'Échec de la génération locale.' }
      }
      if (progress.step === 'done') {
        let resultResponse: Response
        try {
          resultResponse = await fetch(
            `http://127.0.0.1:${info.port}/video/build-result?slug=${encodeURIComponent(context.slug)}`,
            { headers: { 'X-Sidecar-Token': info.token } },
          )
        } catch {
          return { status: 'failed', message: 'Résultat de la génération inaccessible.' }
        }
        if (!resultResponse.ok) {
          return { status: 'failed', message: await AssistantSidecarService.readSidecarError(resultResponse) }
        }
        try {
          return { status: 'done', blob: await resultResponse.blob() }
        } catch (error) {
          return {
            status: 'failed',
            message: error instanceof Error ? error.message : 'Lecture du résultat impossible.',
          }
        }
      }
    }
    return { status: 'failed', message: 'Génération trop longue — réessayez.' }
  }

  /**
   * Current phase of a local build (polled by the progress modal). Shared build endpoint, keyed by slug.
   * @param info - The sidecar coordinates.
   * @param slug - Slug of the assistant being rendered.
   * @returns The reported phase, or null when unreachable.
   */
  private static async getBuildProgress(
    info: NonNullable<Awaited<ReturnType<typeof getScraperSidecarInfo>>>,
    slug: string,
  ): Promise<VideoBuildProgress | null> {
    try {
      const response: Response = await fetch(
        `http://127.0.0.1:${info.port}/video/build-progress?slug=${encodeURIComponent(slug)}`,
        { headers: { 'X-Sidecar-Token': info.token } },
      )
      if (!response.ok) return null
      const body: { step?: string; message?: string; reason?: string | null; updated_at?: number } =
        await response.json()
      return {
        step: body.step ?? 'unknown',
        message: body.message ?? '',
        reason: body.reason ?? null,
        updatedAt: body.updated_at ?? 0,
      }
    } catch {
      return null
    }
  }

  /**
   * Extract the most precise message a failed sidecar response offers.
   * @param response - The failed response.
   * @returns The sidecar `detail` field, or the raw body / status text.
   */
  private static async readSidecarError(response: Response): Promise<string> {
    const raw: string = await response.text().catch((): string => '')
    if (!raw) return `Génération locale : erreur ${response.status}`
    try {
      return (JSON.parse(raw).detail as string) || raw
    } catch {
      return raw
    }
  }
}
