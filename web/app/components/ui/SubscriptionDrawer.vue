<template>
  <Teleport to="body">
    <Transition name="drawer-panel">
      <div
        v-if="open && subscription"
        class="fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[480px] flex-col border-l border-[var(--app-line)] bg-[var(--app-surface)] pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
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
            <UIcon name="i-lucide-repeat" class="h-4 w-4 text-[var(--app-ink-soft)]" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="mb-1 flex flex-wrap items-center gap-1.5">
              <span :class="['inline-flex items-center rounded px-2 py-0.5 text-[10px] font-medium', statusBadgeClass]">
                {{ statusLabel }}
              </span>
            </div>
            <h2 class="truncate text-base leading-tight font-semibold text-[var(--app-ink)]">
              {{ subscription.business_name || 'Réceptionniste IA' }}
            </h2>
            <p class="mt-0.5 text-sm font-semibold text-[var(--app-accent-ink)]">{{ planLabel }}</p>
          </div>
          <button
            class="flex h-7 w-7 items-center justify-center rounded text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
            aria-label="Fermer"
            @click="emit('close')"
          >
            <UIcon name="i-lucide-x" class="h-4 w-4" />
          </button>
        </div>

        <div class="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          <section>
            <h3 class="app-label mb-2">Client</h3>
            <dl class="space-y-1 text-sm">
              <div class="flex justify-between gap-3">
                <dt class="text-muted">Nom</dt>
                <dd class="truncate text-[var(--app-ink)]">{{ subscription.client_name || '—' }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-muted">Email</dt>
                <dd class="truncate text-[var(--app-ink)]">{{ subscription.client_email || '—' }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-muted">Assistant</dt>
                <dd class="truncate text-[var(--app-ink)]">{{ subscription.assistant_name || '—' }}</dd>
              </div>
            </dl>
          </section>

          <section>
            <h3 class="app-label mb-2">Abonnement</h3>
            <dl class="space-y-1 text-sm">
              <div class="flex justify-between gap-3">
                <dt class="text-muted">Formule</dt>
                <dd class="text-[var(--app-ink)]">{{ planLabel }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-muted">Statut</dt>
                <dd class="text-[var(--app-ink)]">{{ statusLabel }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-muted">Depuis</dt>
                <dd class="text-[var(--app-ink)]">{{ formatShortMonthDate(subscription.created_at) }}</dd>
              </div>
              <div v-if="subscription.current_period_end" class="flex justify-between gap-3">
                <dt class="text-muted">Prochaine échéance</dt>
                <dd class="text-[var(--app-ink)]">{{ formatShortMonthDate(subscription.current_period_end) }}</dd>
              </div>
              <div v-if="subscription.canceled_at" class="flex justify-between gap-3">
                <dt class="text-muted">Annulé le</dt>
                <dd class="text-[var(--app-ink)]">{{ formatShortMonthDate(subscription.canceled_at) }}</dd>
              </div>
            </dl>
          </section>

          <a
            v-if="stripeUrl"
            :href="stripeUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="btn-secondary h-9 w-full justify-center text-xs"
          >
            <UIcon name="i-lucide-external-link" class="mr-1.5 h-4 w-4" />
            Ouvrir dans Stripe
          </a>
        </div>

        <div v-if="canManageSubscription" class="space-y-2 border-t border-[var(--app-line)] px-5 py-4">
          <button
            type="button"
            class="btn-secondary h-9 w-full justify-center text-xs"
            :disabled="isBusy"
            @click="refundConfirmModal?.open()"
          >
            <UIcon name="i-lucide-rotate-ccw" class="mr-1.5 h-4 w-4" />
            Rembourser le dernier paiement
          </button>
          <button
            type="button"
            class="flex h-9 w-full items-center justify-center rounded-lg border border-[var(--app-red)] text-xs font-medium text-[var(--app-red)] transition-colors hover:bg-[var(--app-red-soft)] disabled:opacity-50"
            :disabled="isBusy"
            @click="cancelConfirmModal?.open()"
          >
            <UIcon name="i-lucide-x-circle" class="mr-1.5 h-4 w-4" />
            Annuler l'abonnement
          </button>
        </div>
      </div>
    </Transition>

    <UiConfirmModal
      ref="cancelConfirmModal"
      title="Annuler l'abonnement"
      message="Le client cessera d'être facturé. L'assistant reste en ligne. Action immédiate côté Stripe."
      confirm-text="Annuler l'abonnement"
      cancel-text="Retour"
      @confirm="handleCancel"
    />
    <UiConfirmModal
      ref="refundConfirmModal"
      title="Rembourser le dernier paiement"
      message="Rembourse le dernier prélèvement au client (« satisfait ou remboursé »). N'annule pas l'abonnement."
      confirm-text="Rembourser"
      cancel-text="Retour"
      @confirm="handleRefund"
    />
  </Teleport>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AssistantSubscription } from '~/types/AiAssistant'
import type { UiSubscriptionDrawerEmits, UiSubscriptionDrawerProps } from '~/types/UiSubscriptionDrawer'
import type { UseToastReturn } from '~/types/Composables'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useToast } from '~/composables/useToast'
import { formatShortMonthDate } from '~/utils/date'
import { formatEuros } from '~/utils/currency'

/** Detail drawer for one assistant subscription: view + cancel/refund. */
const props: UiSubscriptionDrawerProps = defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  subscription: {
    type: Object as PropType<AssistantSubscription | null>,
    default: null,
  },
  showBack: {
    type: Boolean,
    default: false,
  },
})

const emit: EmitFn<UiSubscriptionDrawerEmits> = defineEmits<UiSubscriptionDrawerEmits>()

const toast: UseToastReturn = useToast()
const isBusy: Ref<boolean> = ref(false)
const cancelConfirmModal: Ref<{ open: () => void } | null> = ref(null)
const refundConfirmModal: Ref<{ open: () => void } | null> = ref(null)

/** A subscription still live on Stripe (active or past-due) can be canceled or refunded from here. */
const canManageSubscription: ComputedRef<boolean> = computed(
  (): boolean => props.subscription?.status === 'active' || props.subscription?.status === 'past_due',
)

/** French label of the subscription status. */
const statusLabel: ComputedRef<string> = computed((): string => {
  const labels: Record<string, string> = {
    active: 'Actif',
    past_due: 'Paiement en retard',
    canceled: 'Annulé',
    incomplete: 'En attente de paiement',
  }
  return labels[props.subscription?.status ?? ''] ?? props.subscription?.status ?? '—'
})

/** Badge colour for the subscription status. */
const statusBadgeClass: ComputedRef<string> = computed((): string => {
  const status: string = props.subscription?.status ?? ''
  if (status === 'active') return 'border border-[var(--app-green)]/40 bg-[var(--app-green)]/10 text-[var(--app-green)]'
  if (status === 'past_due')
    return 'border border-[var(--app-accent)]/40 bg-[var(--app-accent)]/10 text-[var(--app-accent)]'
  return 'border border-[var(--app-line)] bg-[var(--app-surface)] text-[var(--app-ink-soft)]'
})

/** The plan as « 29 €/mois » / « 290 €/an ». */
const planLabel: ComputedRef<string> = computed((): string => {
  const subscription: AssistantSubscription | null = props.subscription
  if (!subscription) return ''
  return `${formatEuros(subscription.amount_cents)}/${subscription.interval === 'year' ? 'an' : 'mois'}`
})

/** Link to the subscription in the Stripe dashboard, when it reached Stripe. */
const stripeUrl: ComputedRef<string | null> = computed((): string | null =>
  props.subscription?.stripe_subscription_id
    ? `https://dashboard.stripe.com/subscriptions/${props.subscription.stripe_subscription_id}`
    : null,
)

/**
 * Run a subscription action with a busy state + error toast; emit `updated` with the refreshed row.
 * @param action - The service call returning the updated subscription, or null (e.g. a refund).
 * @param successMessage - The toast shown on success.
 * @returns A promise resolved once the action finishes.
 */
async function runAction(action: () => Promise<AssistantSubscription | null>, successMessage: string): Promise<void> {
  if (!props.subscription || isBusy.value) return
  isBusy.value = true
  try {
    const updated: AssistantSubscription | null = await action()
    if (updated) emit('updated', updated)
    toast.success(successMessage)
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Une erreur est survenue.')
  } finally {
    isBusy.value = false
  }
}

/**
 * Cancel the subscription (confirmed).
 * @returns A promise resolved once the cancel is attempted.
 */
async function handleCancel(): Promise<void> {
  const id: number | undefined = props.subscription?.id
  if (id === undefined) return
  await runAction(() => AiAssistantService.cancelSubscription(id), 'Abonnement annulé.')
}

/**
 * Refund the subscription's last payment (confirmed).
 * @returns A promise resolved once the refund is attempted.
 */
async function handleRefund(): Promise<void> {
  const id: number | undefined = props.subscription?.id
  if (id === undefined) return
  await runAction(async (): Promise<null> => {
    await AiAssistantService.refundSubscription(id)
    return null
  }, 'Dernier paiement remboursé.')
}
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
