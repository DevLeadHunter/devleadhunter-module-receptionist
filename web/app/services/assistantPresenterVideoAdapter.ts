import type { PresenterVideoExampleDemo, PresenterVideoModuleAdapter } from '~/types/PresenterVideoConfig'
import type { PresenterVideoTake } from '~/types/PresenterVideoTake'
import type { PreviewVideoResult } from '~/services/storyblokSidecarService'
import type { AiAssistantListResponse, AiAssistantSummary } from '../types/AiAssistant'
import { ASSISTANT_MODULE_KEY } from '../constants/assistantModule'
import {
  ASSISTANT_PRESENTER_VIDEO_ANCHOR_ID,
  ASSISTANT_PRESENTER_VIDEO_WORDING,
  ASSISTANT_SCRIPT_STORAGE_KEY,
  ASSISTANT_VIDEO_BUILD_PHASES,
} from '../constants/assistantPresenterVideo'
import { AiAssistantService } from './aiAssistantService'
import { AssistantSidecarService } from './assistantSidecarService'
import { buildAssistantScript } from '../utils/assistantProspectionScript'
import { AssistantVideoTimings } from '../utils/assistantVideoTimings'

/**
 * The user's receptionists that can be filmed: the live demos, a sold one is never filmed again.
 * @returns Them as example demos.
 */
async function loadReceptionistExampleDemos(): Promise<PresenterVideoExampleDemo[]> {
  const response: AiAssistantListResponse = await AiAssistantService.list()
  return response.assistants
    .filter((assistant: AiAssistantSummary): boolean => assistant.status === 'active')
    .map(
      (assistant: AiAssistantSummary): PresenterVideoExampleDemo => ({
        id: assistant.id,
        slug: assistant.slug,
        name: assistant.business_name,
      }),
    )
}

/**
 * Render a take on a receptionist with the desktop app; nothing is published.
 * @param assistantId - The receptionist filmed.
 * @param take - The take montaged, with the cut points to use.
 * @returns The rendered mp4, or why it could not be made.
 */
function renderReceptionistPreview(assistantId: number, take: PresenterVideoTake): Promise<PreviewVideoResult> {
  return AssistantSidecarService.buildPreviewVideo(assistantId, AssistantVideoTimings.buildTimings(take), take.id)
}

export const ASSISTANT_PRESENTER_VIDEO_ADAPTER: PresenterVideoModuleAdapter = {
  moduleKey: ASSISTANT_MODULE_KEY,
  sectionAnchorId: ASSISTANT_PRESENTER_VIDEO_ANCHOR_ID,
  wording: ASSISTANT_PRESENTER_VIDEO_WORDING,
  buildPhases: ASSISTANT_VIDEO_BUILD_PHASES,
  scriptStorageKey: ASSISTANT_SCRIPT_STORAGE_KEY,
  fieldIdPrefix: 'receptionist-video',
  middleLayout: {
    kind: 'chapters',
    chapters: AssistantVideoTimings.middleChapters,
    shortMiddleWarning: AssistantVideoTimings.shortMiddleWarning,
  },
  buildDefaultScript: buildAssistantScript,
  renderPreview: renderReceptionistPreview,
  loadExampleDemos: loadReceptionistExampleDemos,
}
