<template>
  <button
    type="button"
    class="cs-row"
    :class="{ 'cs-row--unread': isPending, 'cs-row--active': props.active }"
    @click="emit('select', props.request.id)"
  >
    <span class="cs-avatar">{{ initials }}</span>
    <span class="cs-row__body">
      <span class="cs-row__top">
        <span class="cs-row__name">{{ props.request.name }}</span>
        <span class="cs-row__status" :class="`cs-row__status--${status.tone}`">{{ status.label }}</span>
      </span>
      <span class="cs-row__meta">
        <span><ClientSpaceIcon name="clock" />{{ timeLabel }}</span>
        <span v-if="props.request.channel === 'email'"><ClientSpaceIcon name="mail" />par e-mail</span>
        <span v-if="props.request.received_outside_hours">hors horaires</span>
        <span v-if="props.request.photo_urls.length > 0"><ClientSpaceIcon name="camera" />{{ photosLabel }}</span>
        <span v-if="appointmentLabel"><ClientSpaceIcon name="calendar" />{{ appointmentLabel }}</span>
      </span>
      <span v-if="props.request.summary" class="cs-row__preview">{{ props.request.summary }}</span>
    </span>
  </button>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientRequest } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceRequestStatus } from '~/types/ClientSpaceRequestList'
import type { ClientSpaceRequestRowEmits, ClientSpaceRequestRowProps } from '~/types/ClientSpaceRequestRow'
import { ClientSpaceRequestUtils } from '~/utils/ClientSpaceRequestUtils'

/**
 * One request in a list: the visitor's initials, its name, what it is at the right, when it came and what it
 * carries, then two lines of what the visitor wants. Tapping opens it.
 * @param request The request.
 * @param active Open beside the list on a wide screen.
 */
const props: ClientSpaceRequestRowProps = defineProps({
  request: { type: Object as PropType<AiAssistantClientRequest>, required: true },
  active: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceRequestRowEmits> = defineEmits<ClientSpaceRequestRowEmits>()

const initials: ComputedRef<string> = computed((): string => ClientSpaceRequestUtils.initials(props.request.name))

const status: ComputedRef<ClientSpaceRequestStatus> = computed((): ClientSpaceRequestStatus =>
  ClientSpaceRequestUtils.status(props.request),
)

const isPending: ComputedRef<boolean> = computed((): boolean => props.request.status === 'new')

/** The time alone when the list is grouped by day, the whole label for an API without the split. */
const timeLabel: ComputedRef<string> = computed(
  (): string => props.request.received_time || props.request.received_label,
)

const photosLabel: ComputedRef<string> = computed((): string =>
  props.request.photo_urls.length === 1 ? '1 photo' : `${props.request.photo_urls.length} photos`,
)

/** The appointment booked, else the half-days wished. */
const appointmentLabel: ComputedRef<string> = computed((): string => {
  if (props.request.appointment_booked) return props.request.appointment_booked
  return props.request.appointment_slots.join(' ou ')
})
</script>

<!-- The row's styles are shared atoms (assets/css/client-space.css): the receptionist's question rows reuse them. -->
