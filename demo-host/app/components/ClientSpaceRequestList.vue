<template>
  <div class="cs-list">
    <div class="cs-seg" role="group" aria-label="Filtre">
      <button
        v-for="option in FILTERS"
        :key="option.value"
        type="button"
        class="cs-seg__item"
        :aria-pressed="filter === option.value"
        @click="filter = option.value"
      >
        {{ option.label }}
        <b v-if="option.value === 'pending' && pendingCount > 0">{{ pendingCount }}</b>
      </button>
    </div>

    <template v-if="showQuestions">
      <p class="cs-day">Questions de {{ props.assistantName }}</p>
      <div class="cs-block">
        <button
          v-for="(entry, index) in props.unanswered"
          :key="entry.question"
          type="button"
          class="cs-row cs-row--unread cs-list__question"
          :class="{ 'cs-row--active': index === props.activeQuestionIndex }"
          @click="emit('open-question', index)"
        >
          <span class="cs-avatar cs-avatar--portrait">
            <AssistantAvatar
              :url="props.portraitUrl"
              :fallback-url="props.portraitFallbackUrl"
              :alt="props.assistantName"
            />
          </span>
          <span class="cs-row__body">
            <span class="cs-row__top">
              <span class="cs-row__name">{{ props.assistantName }}</span>
              <span class="cs-row__status cs-row__status--grey">Question</span>
            </span>
            <span class="cs-row__meta"
              ><span>{{ askedLabel(entry.count) }}</span></span
            >
            <span class="cs-row__preview">{{ entry.question }}</span>
          </span>
        </button>
      </div>
    </template>

    <template v-for="group in groups" :key="group.day">
      <p class="cs-day">{{ group.label }}</p>
      <div class="cs-block">
        <ClientSpaceRequestRow
          v-for="item in group.requests"
          :key="item.id"
          :request="item"
          :active="item.id === props.activeRequestId"
          @select="emit('open', item.id)"
        />
      </div>
    </template>

    <p v-if="groups.length === 0 && !showQuestions" class="cs-list__empty">
      {{ emptyLabel }}
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AiAssistantClientRequest, AiAssistantClientUnansweredEntry } from '~/types/AiAssistantClientSpace'
import type {
  ClientSpaceRequestDayGroup,
  ClientSpaceRequestFilter,
  ClientSpaceRequestListEmits,
  ClientSpaceRequestListProps,
} from '~/types/ClientSpaceRequestList'
import { ClientSpaceRequestUtils } from '~/utils/ClientSpaceRequestUtils'

/** The three filters, in order. */
const FILTERS: { value: ClientSpaceRequestFilter; label: string }[] = [
  { value: 'pending', label: 'À rappeler' },
  { value: 'done', label: 'Rappelées' },
  { value: 'all', label: 'Toutes' },
]

/**
 * The requests of the business, grouped by day, the ones waiting for a call back first; the receptionist's own
 * questions sit at the top, as if she had written in. Tapping a line opens it.
 * @param requests The latest requests, newest first.
 * @param unanswered The questions the receptionist could not answer.
 * @param assistantName The receptionist's first name.
 * @param portraitUrl Her photo.
 * @param portraitFallbackUrl The bust drawn when the photo is missing.
 * @param activeRequestId The request open beside the list on a wide screen.
 * @param activeQuestionIndex The question open beside the list on a wide screen.
 */
const props: ClientSpaceRequestListProps = defineProps({
  requests: { type: Array as PropType<AiAssistantClientRequest[]>, required: true },
  unanswered: { type: Array as PropType<AiAssistantClientUnansweredEntry[]>, required: true },
  assistantName: { type: String, required: true },
  portraitUrl: { type: String, required: true },
  portraitFallbackUrl: { type: String, required: true },
  activeRequestId: { type: Number as PropType<number | null>, default: null },
  activeQuestionIndex: { type: Number as PropType<number | null>, default: null },
})

const emit: EmitFn<ClientSpaceRequestListEmits> = defineEmits<ClientSpaceRequestListEmits>()

const filter: Ref<ClientSpaceRequestFilter> = ref('pending')

const pendingCount: ComputedRef<number> = computed(
  (): number => props.requests.filter((item: AiAssistantClientRequest): boolean => item.status === 'new').length,
)

const shown: ComputedRef<AiAssistantClientRequest[]> = computed((): AiAssistantClientRequest[] => {
  if (filter.value === 'all') return props.requests
  const pending: boolean = filter.value === 'pending'
  return props.requests.filter((item: AiAssistantClientRequest): boolean => (item.status === 'new') === pending)
})

const groups: ComputedRef<ClientSpaceRequestDayGroup[]> = computed((): ClientSpaceRequestDayGroup[] =>
  ClientSpaceRequestUtils.groupByDay(shown.value),
)

/** The receptionist's questions belong with what waits, never with what is done. */
const showQuestions: ComputedRef<boolean> = computed(
  (): boolean => filter.value !== 'done' && props.unanswered.length > 0,
)

const emptyLabel: ComputedRef<string> = computed((): string => {
  if (filter.value === 'pending') return 'Personne à rappeler pour le moment.'
  if (filter.value === 'done') return 'Aucune demande rappelée pour le moment.'
  return 'Aucune demande pour le moment : elles arrivent ici dès qu’un visiteur laisse ses coordonnées.'
})

/**
 * How often visitors asked a question.
 * @param count The count.
 * @returns « posée 3 fois », « posée 1 fois ».
 */
function askedLabel(count: number): string {
  return count > 1 ? `posée ${count} fois` : 'posée 1 fois'
}
</script>

<style scoped>
.cs-list {
  display: grid;
  align-content: start;
}

.cs-list__question {
  align-items: flex-start;
}

.cs-list__empty {
  margin: 0;
  padding: 28px 16px;
  font-size: 14.5px;
  line-height: 1.5;
  color: var(--cs-dim);
}
</style>
