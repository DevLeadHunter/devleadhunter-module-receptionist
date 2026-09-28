<template>
  <div class="cs-screen__body">
    <p class="cs-sec">Votre abonnement</p>
    <div class="cs-block">
      <p v-if="!props.subscription" class="cs-text cs-text--dim">Aucun abonnement enregistré.</p>
      <template v-else>
        <p class="cs-text">
          <b>{{ props.subscription.price_label }}</b> · {{ statusLabel }}
          <template v-if="periodEndLine"><br />{{ periodEndLine }}</template>
        </p>
        <div v-if="props.subscription.can_manage && !props.readOnly" class="cs-screen__actions">
          <button
            type="button"
            class="cs-btn"
            :disabled="props.isOpeningBillingPortal"
            @click="emit('open-billing-portal')"
          >
            <ClientSpaceIcon name="external-link" />
            {{ props.isOpeningBillingPortal ? 'Ouverture…' : 'Factures, carte bancaire, résiliation' }}
          </button>
          <p v-if="props.billingPortalError" class="cs-notice cs-notice--error">{{ props.billingPortalError }}</p>
        </div>
      </template>
    </div>
    <p class="cs-sec">Bon à savoir</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        Sans engagement : la résiliation prend effet à la fin du mois en cours. Le premier mois est satisfait ou
        remboursé.
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientSubscription } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceSubscriptionEmits, ClientSpaceSubscriptionProps } from '~/types/ClientSpaceSubscription'
import { CLIENT_SPACE_SUBSCRIPTION_STATUS_LABELS } from '~/constants/ClientSpaceSubscriptionStatuses'

const props: ClientSpaceSubscriptionProps = defineProps({
  subscription: { type: Object as PropType<AiAssistantClientSubscription | null>, default: null },
  isOpeningBillingPortal: { type: Boolean, default: false },
  billingPortalError: { type: String as PropType<string | null>, default: null },
  readOnly: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceSubscriptionEmits> = defineEmits<ClientSpaceSubscriptionEmits>()

const statusLabel: ComputedRef<string> = computed((): string =>
  props.subscription ? CLIENT_SPACE_SUBSCRIPTION_STATUS_LABELS[props.subscription.status].toLowerCase() : '',
)

/** The date that matters: the access end of a cancelled subscription, the due date, or the next renewal. */
const periodEndLine: ComputedRef<string> = computed((): string => {
  const subscription: AiAssistantClientSubscription | null = props.subscription
  if (!subscription?.period_end_label) return ''
  if (subscription.status === 'canceled' || subscription.cancel_scheduled) {
    return `Résiliation prévue, accès jusqu’au ${subscription.period_end_label}.`
  }
  if (subscription.status === 'past_due') return `Échéance du ${subscription.period_end_label}.`
  return `Prochain renouvellement le ${subscription.period_end_label}.`
})
</script>
