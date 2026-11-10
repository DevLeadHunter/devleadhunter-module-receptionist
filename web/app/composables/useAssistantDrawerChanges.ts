import type { ComputedRef } from 'vue'
import type { DrawerStackEntry } from '~/types/DrawerStack'
import type { AiAssistantRequestItem, AiAssistantSummary, AssistantSubscription } from '../types/AiAssistant'
import type {
  AssistantMutationNotice,
  AssistantRequestMutationNotice,
  AssistantSubscriptionMutationNotice,
} from '../types/AssistantDrawerStack'
import { computed } from 'vue'
import { useDrawerStackStore } from '~/stores/drawerStack'

/** What `useAssistantDrawerChanges` gives: the receptionist's change counts and latest notices, and how to send one. */
export type UseAssistantDrawerChangesReturn = {
  assistantChangeCount: ComputedRef<number>
  latestAssistantChange: ComputedRef<AssistantMutationNotice | null>
  requestChangeCount: ComputedRef<number>
  latestRequestChange: ComputedRef<AssistantRequestMutationNotice | null>
  subscriptionChangeCount: ComputedRef<number>
  latestSubscriptionChange: ComputedRef<AssistantSubscriptionMutationNotice | null>
  notifyAssistantUpdated: (assistant: AiAssistantSummary) => void
  notifyAssistantDeleted: (assistantId: number) => void
  notifyAssistantRequestUpdated: (request: AiAssistantRequestItem) => void
  notifySubscriptionUpdated: (subscription: AssistantSubscription) => void
}

/**
 * The receptionist's changes broadcast through the core drawer stack, to its stacked drawers and its pages.
 * @returns The counts and latest notices to watch, and the functions that broadcast a change.
 */
export function useAssistantDrawerChanges(): UseAssistantDrawerChangesReturn {
  const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()

  /**
   * Show an updated assistant in its stacked drawers and tell the pages.
   * @param assistant - The assistant as the API returned it.
   */
  function notifyAssistantUpdated(assistant: AiAssistantSummary): void {
    drawerStack.replaceEntries((entry: DrawerStackEntry): DrawerStackEntry => {
      if (
        (entry.kind === 'assistant-conversations' || entry.kind === 'assistant-sources') &&
        entry.assistant.id === assistant.id
      ) {
        return { ...entry, assistant }
      }
      return entry
    })
    drawerStack.broadcastChange('assistants', { type: 'updated', assistant })
  }

  /**
   * Close the stacked drawers of a deleted assistant and tell the pages.
   * @param assistantId - Identifier of the deleted assistant.
   */
  function notifyAssistantDeleted(assistantId: number): void {
    drawerStack.replaceEntries((entry: DrawerStackEntry): DrawerStackEntry | null => {
      const showsAssistant: boolean =
        (entry.kind === 'assistant-conversations' || entry.kind === 'assistant-sources') &&
        entry.assistant.id === assistantId
      return showsAssistant ? null : entry
    })
    drawerStack.broadcastChange('assistants', { type: 'deleted', assistantId })
  }

  /**
   * Show a changed visitor request (status, note) in its drawer and tell the pages.
   * @param request - The request as the API returned it.
   */
  function notifyAssistantRequestUpdated(request: AiAssistantRequestItem): void {
    drawerStack.replaceEntries(
      (entry: DrawerStackEntry): DrawerStackEntry =>
        entry.kind === 'assistant-request' && entry.request.id === request.id ? { ...entry, request } : entry,
    )
    drawerStack.broadcastChange('assistant-requests', { type: 'updated', request })
  }

  /**
   * Show an updated subscription in its drawer and tell the pages.
   * @param subscription - The subscription as the API returned it.
   */
  function notifySubscriptionUpdated(subscription: AssistantSubscription): void {
    drawerStack.replaceEntries(
      (entry: DrawerStackEntry): DrawerStackEntry =>
        entry.kind === 'assistant-subscription' && entry.subscription.id === subscription.id
          ? { ...entry, subscription }
          : entry,
    )
    drawerStack.broadcastChange('assistant-subscriptions', { type: 'updated', subscription })
  }

  return {
    assistantChangeCount: computed((): number => drawerStack.changeCountOf('assistants')),
    latestAssistantChange: computed((): AssistantMutationNotice | null => drawerStack.latestChangeOf('assistants')),
    requestChangeCount: computed((): number => drawerStack.changeCountOf('assistant-requests')),
    latestRequestChange: computed((): AssistantRequestMutationNotice | null =>
      drawerStack.latestChangeOf('assistant-requests'),
    ),
    subscriptionChangeCount: computed((): number => drawerStack.changeCountOf('assistant-subscriptions')),
    latestSubscriptionChange: computed((): AssistantSubscriptionMutationNotice | null =>
      drawerStack.latestChangeOf('assistant-subscriptions'),
    ),
    notifyAssistantUpdated,
    notifyAssistantDeleted,
    notifyAssistantRequestUpdated,
    notifySubscriptionUpdated,
  }
}
