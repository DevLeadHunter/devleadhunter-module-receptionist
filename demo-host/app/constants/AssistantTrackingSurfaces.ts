import type { DemoTrackingSurface } from '~/types/demoTracking'
import type { DemoVideoSurface } from '~/types/demoVideoTracking'

export const ASSISTANT_TRACKING_SURFACE: DemoTrackingSurface = { name: 'assistant', shouldTrackInsideFrame: true }

export const ASSISTANT_VIDEO_SURFACE: DemoVideoSurface = { name: 'assistant', eventPrefix: 'assistant_video_' }
