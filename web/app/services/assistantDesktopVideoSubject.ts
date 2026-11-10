import type { DesktopVideoRequest, DesktopVideoSubjectRelay } from '~/types/DesktopVideoRelay'
import type { FullVideoBuildResult } from '~/services/storyblokSidecarService'
import type { AiAssistantDesktopVideoRequest } from '../types/AiAssistant'
import { ASSISTANT_MODULE_KEY } from '../constants/assistantModule'
import { AiAssistantService } from './aiAssistantService'
import { AssistantSidecarService } from './assistantSidecarService'

export const ASSISTANT_DESKTOP_VIDEO_SUBJECT: DesktopVideoSubjectRelay = {
  kind: 'assistant',
  moduleKey: ASSISTANT_MODULE_KEY,
  listWaitingRequests: async (): Promise<DesktopVideoRequest[]> => {
    const assistantRequests: AiAssistantDesktopVideoRequest[] = await AiAssistantService.listDesktopVideoRequests()
    return assistantRequests.map(
      (request: AiAssistantDesktopVideoRequest): DesktopVideoRequest => ({
        kind: 'assistant',
        subjectId: request.assistant_id,
        businessName: request.business_name,
        requestedAt: request.requested_at,
      }),
    )
  },
  describeVideo: (businessName: string): string => `Vidéo de la réceptionniste de « ${businessName} »`,
  claim: async (subjectId: number): Promise<void> => {
    await AiAssistantService.claimDesktopVideo(subjectId)
  },
  build: (subjectId: number): Promise<FullVideoBuildResult> => AssistantSidecarService.buildFullVideo(subjectId),
  reportFailure: async (subjectId: number, message: string): Promise<void> => {
    await AiAssistantService.reportDesktopVideoFailure(subjectId, message)
  },
}
