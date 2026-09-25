<template>
  <div class="card overflow-hidden p-0">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--app-line)] px-5 py-4">
      <div>
        <h2 class="font-semibold text-[var(--app-ink)]">Dernières demandes</h2>
        <p class="text-xs text-[var(--app-ink-soft)]">Ce que les visiteurs ont laissé à {{ props.assistantName }}.</p>
      </div>
      <NuxtLink
        :to="`/dashboard/ai-assistants/requests?assistant=${props.assistantId}`"
        class="btn-secondary h-8 text-xs"
      >
        Toutes les demandes
      </NuxtLink>
    </div>
    <p v-if="props.requests.length === 0" class="px-5 py-8 text-center text-sm text-[var(--app-ink-soft)]">
      Aucune demande pour l'instant.
    </p>
    <ul v-else class="divide-y divide-[var(--app-line-soft)]">
      <li v-for="request in props.requests" :key="request.id">
        <button
          type="button"
          class="flex w-full cursor-pointer items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-[var(--app-surface-2)]"
          @click="emit('open', request)"
        >
          <span class="app-badge shrink-0" :class="request.type === 'urgent' ? 'app-badge--danger' : ''">
            {{ REQUEST_TYPE_LABELS[request.type] }}
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-medium text-[var(--app-ink)]">{{ request.name }}</span>
            <span class="block truncate text-xs text-[var(--app-ink-soft)]">
              {{ request.need_summary || request.need || 'Demande de rappel, sans détail.' }}
            </span>
          </span>
          <span class="shrink-0 text-xs text-[var(--app-ink-soft)] tabular-nums">
            {{ formatShortMonthDayTime(request.created_at) }}
          </span>
          <span :class="['app-badge shrink-0', REQUEST_STATUS_BADGE_CLASS[request.status]]">
            {{ REQUEST_STATUS_LABELS[request.status] }}
          </span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AiAssistantRequestItem, AiAssistantRequestStatus } from '~/types/AiAssistant'
import type { AssistantRecentRequestsEmits, AssistantRecentRequestsProps } from '~/types/AssistantRecentRequests'
import { REQUEST_STATUS_LABELS, REQUEST_TYPE_LABELS } from '~/utils/aiAssistantLabels'
import { formatShortMonthDayTime } from '~/utils/date'

const props: AssistantRecentRequestsProps = defineProps({
  assistantId: {
    type: Number,
    required: true,
  },
  assistantName: {
    type: String,
    required: true,
  },
  requests: {
    type: Array as PropType<AiAssistantRequestItem[]>,
    required: true,
  },
})

const emit: EmitFn<AssistantRecentRequestsEmits> = defineEmits<AssistantRecentRequestsEmits>()

/** Badge tone of each request status: the ones still waiting stand out. */
const REQUEST_STATUS_BADGE_CLASS: Record<AiAssistantRequestStatus, string> = {
  new: 'app-badge--strong',
  handled: 'app-badge--success',
  dropped: '',
}
</script>
