<template>
  <Teleport to="body">
    <Transition name="drawer-panel">
      <div
        v-if="open && assistant"
        class="fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[520px] flex-col border-l border-[var(--app-line)] bg-[var(--app-surface)] pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
      >
        <div class="flex items-start gap-3 border-b border-[var(--app-line)] px-5 py-4">
          <button
            v-if="showBack"
            class="flex h-10 w-7 shrink-0 items-center justify-center rounded text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
            title="Revenir au volet précédent"
            @click="emit('back')"
          >
            <UIcon name="i-lucide-chevron-left" class="h-4 w-4" />
          </button>
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--app-line)] bg-[var(--app-surface)]"
          >
            <UIcon name="i-lucide-messages-square" class="h-4 w-4 text-[var(--app-ink-soft)]" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 class="truncate text-base leading-tight font-semibold text-[var(--app-ink)]">
              Ce que vos visiteurs ont demandé
            </h2>
            <p class="text-muted mt-0.5 truncate text-sm">
              {{ assistant.business_name }} · {{ assistant.assistant_name }}
            </p>
          </div>
          <button
            class="flex h-7 w-7 items-center justify-center rounded text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
            aria-label="Fermer"
            @click="emit('close')"
          >
            <UIcon name="i-lucide-x" class="h-4 w-4" />
          </button>
        </div>

        <div class="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <p v-if="isLoading" class="text-muted text-sm">Chargement…</p>
          <p v-else-if="conversations.length === 0" class="text-muted text-sm leading-relaxed">
            Aucune conversation pour le moment. Chaque échange d'un visiteur avec {{ assistant.assistant_name }}
            apparaîtra ici (les 20 dernières, conservées 90 jours).
          </p>
          <article v-for="conversation in conversations" :key="conversation.id" class="app-card overflow-hidden">
            <header
              class="flex items-center justify-between gap-3 border-b border-[var(--app-line-soft)] px-4 py-2 text-xs"
            >
              <span class="text-[var(--app-ink)] tabular-nums">{{
                formatNumericDateTime(conversation.started_at)
              }}</span>
              <span class="text-muted tabular-nums">{{ conversationMetaLabel(conversation) }}</span>
            </header>
            <ul class="space-y-2 px-4 py-3">
              <li
                v-for="message in conversation.messages"
                :key="message.id"
                class="flex"
                :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
              >
                <p
                  class="max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-line"
                  :class="
                    message.role === 'user'
                      ? 'bg-[var(--app-ink)] text-[var(--app-surface)]'
                      : 'bg-[var(--app-surface-2)] text-[var(--app-ink)]'
                  "
                >
                  {{ message.content }}
                </p>
              </li>
            </ul>
          </article>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType, Ref } from 'vue'
import { ref, watch } from 'vue'
import type { AiAssistantConversation, AiAssistantConversationsResponse, AiAssistantSummary } from '~/types/AiAssistant'
import type {
  UiAssistantConversationsDrawerEmits,
  UiAssistantConversationsDrawerProps,
} from '~/types/UiAssistantConversationsDrawer'
import { AiAssistantService } from '~/services/aiAssistantService'
import { formatNumericDateTime } from '~/utils/date'

const props: UiAssistantConversationsDrawerProps = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  assistant: {
    type: Object as PropType<AiAssistantSummary | null>,
    default: null,
  },
  showBack: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<UiAssistantConversationsDrawerEmits> = defineEmits<UiAssistantConversationsDrawerEmits>()

const conversations: Ref<AiAssistantConversation[]> = ref([])
const isLoading: Ref<boolean> = ref(false)

/**
 * Load the assistant's latest conversations.
 * @param assistantId - The assistant whose journal to show.
 * @returns A promise resolved once the list is loaded.
 */
async function loadConversations(assistantId: number): Promise<void> {
  isLoading.value = true
  try {
    const response: AiAssistantConversationsResponse = await AiAssistantService.listConversations(assistantId)
    conversations.value = response.conversations
  } catch {
    conversations.value = []
  } finally {
    isLoading.value = false
  }
}

/**
 * Message count and language of a conversation, as « 6 messages · DE ».
 * @param conversation - The conversation.
 * @returns The label.
 */
function conversationMetaLabel(conversation: AiAssistantConversation): string {
  const count: string = `${conversation.message_count} message${conversation.message_count > 1 ? 's' : ''}`
  return conversation.language ? `${count} · ${conversation.language.toUpperCase()}` : count
}

watch(
  (): number | null => (props.open && props.assistant ? props.assistant.id : null),
  (assistantId: number | null): void => {
    conversations.value = []
    if (assistantId !== null) void loadConversations(assistantId)
  },
  { immediate: true },
)
</script>

<style scoped>
.drawer-panel-enter-active,
.drawer-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.drawer-panel-enter-from,
.drawer-panel-leave-to {
  transform: translateX(100%);
}
</style>
