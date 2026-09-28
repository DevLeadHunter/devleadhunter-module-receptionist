import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AssistantPhotoReply } from '~/types/AiAssistant'
import type { AssistantConversationThread } from '~/types/AssistantThread'
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
 * @param thread - The conversation thread its parts share.
 * @returns The photos' state and the panel's actions.
 */
export function useAssistantPhotoUpload(thread: AssistantConversationThread): UseAssistantPhotoUploadReturn {
  const photoPreviews: Ref<Record<number, string>> = ref({})
  const photosRemaining: Ref<number> = ref(ASSISTANT_PHOTOS_PER_VISIT)
  const hasSentPhoto: Ref<boolean> = ref(false)
  const leadNeedPrefill: Ref<string> = ref('')

  const isPhotoPanelOpen: ComputedRef<boolean> = computed((): boolean => thread.openPanel.value === 'photo')

  /** Show the photo panel: its privacy note comes before the file picker. */
  function openPhotoPanel(): void {
    if (photosRemaining.value <= 0 || thread.isBusy.value || thread.isAssistantUnavailable.value) return
    thread.noteInlineOpening()
    thread.openPanel.value = 'photo'
  }

  /** Hide the photo panel. */
  function closePhotoPanel(): void {
    if (thread.openPanel.value === 'photo') thread.openPanel.value = null
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
      thread.pushLocalLine(PHOTO_LABELS[thread.language.value].quota)
    } else if (status === 413) {
      thread.pushLocalLine(PHOTO_LABELS[thread.language.value].tooLarge)
    } else if (status === 415) {
      thread.pushLocalLine(PHOTO_LABELS[thread.language.value].invalid)
    } else {
      thread.reportFailure(AssistantRequestUtils.failureOf(error))
    }
  }

  /**
   * Upload a prepared photo and show what the assistant says of it; a refused one stays in the thread as not sent.
   * @param upload - The photo, compressed.
   * @returns A promise resolved once the assistant has answered, or the refusal is told.
   */
  async function uploadPhoto(upload: Blob): Promise<void> {
    thread.messages.value.push({ role: 'user', content: PHOTO_LABELS[thread.language.value].sent })
    const previewIndex: number = thread.messages.value.length - 1
    const previewUrl: string = URL.createObjectURL(upload)
    showPhotoPreview(previewIndex, previewUrl)
    captureDemoEvent('assistant_photo_sent')
    try {
      const form: FormData = new FormData()
      form.append('file', upload, 'photo.jpg')
      form.append('session_id', thread.sessionId.value)
      form.append('language', thread.language.value)
      form.append('internal', String(DemoBeaconUtils.isInternalVisit()))
      const answer: AssistantPhotoReply = await AssistantRequestUtils.sendPhoto(thread.publicEndpoint, form)
      thread.messages.value.push({ role: 'assistant', content: answer.reply })
      photosRemaining.value = answer.remaining
      if (answer.accepted && !thread.hasSentLead.value) {
        hasSentPhoto.value = true
        if (answer.need) leadNeedPrefill.value = answer.need
        thread.openPanel.value = 'lead-form'
      }
    } catch (error: unknown) {
      // A refused photo is not shown as sent: its thumbnail goes, the refusal explains why.
      dropPhotoPreview(previewIndex, previewUrl)
      thread.messages.value[previewIndex] = AssistantThreadUtils.localLine(
        PHOTO_LABELS[thread.language.value].refused,
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
    if (thread.isBusy.value || thread.isAssistantUnavailable.value) return
    if (!PhotoCompressionUtils.isPhoto(file)) {
      thread.pushLocalLine(PHOTO_LABELS[thread.language.value].invalid)
      return
    }
    // Busy from the start: a second photo picked while this one compresses would slip past the quota.
    thread.isBusy.value = true
    try {
      const upload: Blob = await PhotoCompressionUtils.prepare(file)
      if (upload.size > PhotoCompressionUtils.MAX_BYTES) {
        thread.pushLocalLine(PHOTO_LABELS[thread.language.value].tooLarge)
        return
      }
      await uploadPhoto(upload)
    } finally {
      thread.isBusy.value = false
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
