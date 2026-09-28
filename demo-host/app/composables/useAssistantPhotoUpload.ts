import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AssistantPhotoReply } from '~/types/AiAssistant'
import type { AssistantThreadContext } from '~/types/AssistantThread'
import type { UseAssistantPhotoUploadReturn } from '~/types/UseAssistantPhotoUpload'
import { captureDemoEvent } from '~/composables/useDemoTracking'
import { PHOTO_LABELS } from '~/constants/AssistantWidgetLabels'
import { ASSISTANT_PHOTOS_PER_VISIT } from '~/constants/AssistantWidgetLimits'
import { ApiRefusalUtils } from '~/utils/ApiRefusalUtils'
import { AssistantRequestUtils } from '~/utils/AssistantRequestUtils'
import { AssistantThreadUtils } from '~/utils/AssistantThreadUtils'
import { DemoBeaconUtils } from '~/utils/DemoBeaconUtils'
import { PhotoCompressionUtils } from '~/utils/PhotoCompressionUtils'

/**
 * The photo a visitor sends for a quote: the panel with its privacy note, the upload, its thumbnail in the thread.
 * @param context - The state the conversation's parts share.
 * @returns The photos' state and the panel's actions.
 */
export function useAssistantPhotoUpload(context: AssistantThreadContext): UseAssistantPhotoUploadReturn {
  const photoPreviews: Ref<Record<number, string>> = ref({})
  const photosRemaining: Ref<number> = ref(ASSISTANT_PHOTOS_PER_VISIT)
  const hasSentPhoto: Ref<boolean> = ref(false)
  /** What an accepted photo shows, to prefill the need of the contact form. */
  const leadNeedPrefill: Ref<string> = ref('')

  const isPhotoPanelOpen: ComputedRef<boolean> = computed((): boolean => context.openPanel.value === 'photo')

  /** Show the photo panel: its privacy note comes before the file picker. */
  function openPhotoPanel(): void {
    if (photosRemaining.value <= 0 || context.isBusy.value || context.isAssistantUnavailable.value) return
    context.noteInlineOpening()
    context.openPanel.value = 'photo'
  }

  /** Hide the photo panel. */
  function closePhotoPanel(): void {
    if (context.openPanel.value === 'photo') context.openPanel.value = null
  }

  /**
   * Show a photo in the bubble of a message.
   * @param messageIndex - The message's position in the thread.
   * @param url - The photo (an object URL, or a file of the demo).
   */
  function showPhotoPreview(messageIndex: number, url: string): void {
    photoPreviews.value = { ...photoPreviews.value, [messageIndex]: url }
  }

  /**
   * Take a photo's thumbnail out of the thread and free its object URL.
   * @param messageIndex - The message the thumbnail was in.
   * @param url - Its object URL.
   */
  function dropPhotoPreview(messageIndex: number, url: string): void {
    URL.revokeObjectURL(url)
    photoPreviews.value = Object.fromEntries(
      Object.entries(photoPreviews.value).filter(
        ([index]: [string, string]): boolean => Number(index) !== messageIndex,
      ),
    )
  }

  /**
   * Tell the visitor why the API refused their photo (quota, size, format) or could not take it.
   * @param error - What the upload threw.
   */
  function reportPhotoFailure(error: unknown): void {
    const status: number | undefined = ApiRefusalUtils.status(error)
    if (status === 409) {
      photosRemaining.value = 0
      context.pushLocalLine(PHOTO_LABELS[context.language.value].quota)
    } else if (status === 413) {
      context.pushLocalLine(PHOTO_LABELS[context.language.value].tooLarge)
    } else if (status === 415) {
      context.pushLocalLine(PHOTO_LABELS[context.language.value].invalid)
    } else {
      context.reportFailure(AssistantRequestUtils.failureOf(error))
    }
  }

  /**
   * Upload a prepared photo and show what the assistant says of it; a refused one stays in the thread as not sent.
   * @param upload - The photo, compressed.
   * @returns A promise resolved once the assistant has answered, or the refusal is told.
   */
  async function uploadPhoto(upload: Blob): Promise<void> {
    context.messages.value.push({ role: 'user', content: PHOTO_LABELS[context.language.value].sent })
    const previewIndex: number = context.messages.value.length - 1
    const previewUrl: string = URL.createObjectURL(upload)
    showPhotoPreview(previewIndex, previewUrl)
    captureDemoEvent('assistant_photo_sent')
    try {
      const form: FormData = new FormData()
      form.append('file', upload, 'photo.jpg')
      form.append('session_id', context.sessionId.value)
      form.append('language', context.language.value)
      form.append('internal', String(DemoBeaconUtils.isInternalVisit()))
      const answer: AssistantPhotoReply = await AssistantRequestUtils.sendPhoto(context.publicEndpoint, form)
      context.messages.value.push({ role: 'assistant', content: answer.reply })
      photosRemaining.value = answer.remaining
      if (answer.accepted && !context.hasSentLead.value) {
        hasSentPhoto.value = true
        if (answer.need) leadNeedPrefill.value = answer.need
        context.openPanel.value = 'lead-form'
      }
    } catch (error: unknown) {
      // A refused photo is not shown as sent: its thumbnail goes, the refusal explains why.
      dropPhotoPreview(previewIndex, previewUrl)
      context.messages.value[previewIndex] = AssistantThreadUtils.localLine(
        PHOTO_LABELS[context.language.value].refused,
        'user',
      )
      reportPhotoFailure(error)
    }
  }

  /**
   * Send a photo for a quote: thumbnail at once, the assistant's description, then the contact form prefilled.
   * @param file - The picked file.
   * @returns A promise resolved once the assistant has answered.
   */
  async function sendPhoto(file: File): Promise<void> {
    closePhotoPanel()
    if (context.isBusy.value || context.isAssistantUnavailable.value) return
    if (!PhotoCompressionUtils.isPhoto(file)) {
      context.pushLocalLine(PHOTO_LABELS[context.language.value].invalid)
      return
    }
    // Busy from the start: a second photo picked while this one compresses would slip past the quota.
    context.isBusy.value = true
    try {
      const upload: Blob = await PhotoCompressionUtils.prepare(file)
      if (upload.size > PhotoCompressionUtils.MAX_BYTES) {
        context.pushLocalLine(PHOTO_LABELS[context.language.value].tooLarge)
        return
      }
      await uploadPhoto(upload)
    } finally {
      context.isBusy.value = false
    }
  }

  /** Free the thumbnails' object URLs when the widget leaves the page. */
  function releasePhotoPreviews(): void {
    Object.values(photoPreviews.value).forEach((url: string): void => URL.revokeObjectURL(url))
  }

  return {
    photoPreviews,
    photosRemaining,
    hasSentPhoto,
    leadNeedPrefill,
    isPhotoPanelOpen,
    openPhotoPanel,
    closePhotoPanel,
    sendPhoto,
    showPhotoPreview,
    releasePhotoPreviews,
  }
}
