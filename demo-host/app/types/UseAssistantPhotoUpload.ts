import type { ComputedRef, Ref } from 'vue'

export type UseAssistantPhotoUploadReturn = {
  photoPreviews: Ref<Record<number, string>>
  photosRemaining: Ref<number>
  hasSentPhoto: Ref<boolean>
  leadNeedPrefill: Ref<string>
  isPhotoPanelOpen: ComputedRef<boolean>
  openPhotoPanel: () => void
  closePhotoPanel: () => void
  sendPhoto: (file: File) => Promise<void>
  showPhotoPreview: (messageIndex: number, url: string) => void
  releasePhotoPreviews: () => void
}
