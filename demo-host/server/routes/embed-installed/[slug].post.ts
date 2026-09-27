import type { H3Event } from 'h3'
import type { AssistantInstalledPing } from '~/types/AssistantInstalledPing'

/** A hostname as a browser reports it: dotted labels of letters, digits and hyphens, no scheme nor path. */
const HOSTNAME: RegExp = /^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i

/**
 * The embed loader saw itself on a client's website: the sighting goes to the API, which records where and when
 * the widget was last seen (a « Pour démarrer » step of the client space). Mounted at `/embed-installed/{slug}`.
 * Always answers 204: the host page must never notice a failure.
 * @param event - The incoming H3 request event.
 * @returns Nothing.
 */
export default defineEventHandler(async (event: H3Event): Promise<void> => {
  const slug: string = getRouterParam(event, 'slug') ?? ''
  const body: AssistantInstalledPing | null = await readBody<AssistantInstalledPing | null>(event).catch(
    (): null => null,
  )
  const host: string = String(body?.host ?? '')
    .trim()
    .toLowerCase()
  setResponseStatus(event, 204)
  if (!slug || !HOSTNAME.test(host)) return
  const apiBase: string = useRuntimeConfig(event).public.apiBase
  try {
    await $fetch(`${apiBase}/api/v1/ai-assistants/public/${encodeURIComponent(slug)}/installed`, {
      method: 'POST',
      body: { host },
    })
  } catch {
    // The API refused or is down: the next visit reports again.
  }
})
