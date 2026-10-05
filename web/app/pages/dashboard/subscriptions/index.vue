<template>
  <div class="space-y-5">
    <UiPageHeader
      eyebrow="Commercial"
      title="Abonnements"
      description="Vos abonnements Réceptionniste IA : qui paie, combien, et depuis quand. Cliquez pour annuler ou rembourser."
    >
      <template #actions>
        <button
          :disabled="isLoading"
          class="app-btn-secondary h-11 px-4 text-sm whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-50 @2xl:h-9 @2xl:text-xs"
          @click="loadAll"
        >
          <UIcon name="i-lucide-refresh-cw" :class="['h-3.5 w-3.5', isLoading && 'animate-spin']" />
          Actualiser
        </button>
      </template>
    </UiPageHeader>

    <div class="grid grid-cols-2 gap-4">
      <UiStatCard label="Abonnements actifs" :value="activeCount" icon="i-lucide-repeat" accent="emerald" />
      <UiStatCard label="Revenu mensuel (MRR)" :value="formatEuros(mrrCents)" icon="i-lucide-euro" accent="emerald" />
    </div>

    <UiLoader v-if="isLoading" label="Chargement des abonnements…" />

    <UiEmptyState
      v-else-if="subscriptions.length === 0"
      title="Aucun abonnement"
      description="Générez un lien d'abonnement depuis un assistant et envoyez-le à votre client."
    />

    <div v-else class="app-card overflow-hidden">
      <BaseTable min-width="640px">
        <template #head>
          <BaseTableTh>Client</BaseTableTh>
          <BaseTableTh align="right">Formule</BaseTableTh>
          <BaseTableTh align="center">Statut</BaseTableTh>
          <BaseTableTh align="right">Depuis</BaseTableTh>
        </template>

        <BaseTableTr
          v-for="subscription in subscriptions"
          :key="subscription.id"
          class="cursor-pointer"
          @click="openDrawer(subscription)"
          @keydown.enter="openDrawer(subscription)"
        >
          <BaseTableTd>
            <span class="block text-sm font-semibold text-[var(--app-ink)]">
              {{ subscription.business_name || subscription.client_name || `Abonnement #${subscription.id}` }}
            </span>
            <span class="font-label text-xs text-[var(--app-ink-soft)]">
              {{ subscription.client_email || 'Sans contact' }}
            </span>
          </BaseTableTd>

          <BaseTableTd label="Formule" align="right" class="text-sm font-semibold text-[var(--app-ink)] tabular-nums">
            {{ planLabel(subscription) }}
          </BaseTableTd>

          <BaseTableTd label="Statut" align="center">
            <span :class="['app-badge', STATUS_BADGE_CLASS[subscription.status] ?? '']">
              {{ SUBSCRIPTION_STATUS_LABELS[subscription.status] }}
            </span>
          </BaseTableTd>

          <BaseTableTd label="Depuis" align="right" class="font-label text-xs text-[var(--app-ink-soft)]">
            {{ formatShortMonthDate(subscription.created_at) }}
          </BaseTableTd>
        </BaseTableTr>
      </BaseTable>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { Ref } from 'vue'
import { onMounted, ref, watch } from 'vue'
import type { AssistantSubscription, AssistantSubscriptionListResponse } from '~/types/AiAssistant'
import type { AssistantSubscriptionMutationNotice } from '~/types/DrawerStack'
import type { UseToastReturn } from '~/types/Composables'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useDrawerStackStore } from '~/stores/drawerStack'
import { useToast } from '~/composables/useToast'
import { SUBSCRIPTION_STATUS_LABELS } from '~/utils/aiAssistantLabels'
import { formatShortMonthDate } from '~/utils/date'
import { formatEuros } from '~/utils/currency'

definePageMeta({
  layout: 'dashboard',
  middleware: ['auth'],
})

const toast: UseToastReturn = useToast()

const subscriptions: Ref<AssistantSubscription[]> = ref([])
const activeCount: Ref<number> = ref(0)
const mrrCents: Ref<number> = ref(0)
const isLoading: Ref<boolean> = ref(false)

const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()

const STATUS_BADGE_CLASS: Record<string, string> = {
  incomplete: '',
  active: 'app-badge--success',
  past_due: 'app-badge--progress',
  canceled: 'app-badge--danger',
}

/**
 * The plan label (« 29 €/mois » / « 290 €/an »).
 * @param subscription - The subscription row.
 * @returns The formatted plan.
 */
function planLabel(subscription: AssistantSubscription): string {
  return `${formatEuros(subscription.amount_cents)}/${subscription.interval === 'year' ? 'an' : 'mois'}`
}

/**
 * Load the subscriptions + KPIs.
 * @returns A promise resolved once the list is loaded.
 */
async function loadAll(): Promise<void> {
  isLoading.value = true
  try {
    const response: AssistantSubscriptionListResponse = await AiAssistantService.listSubscriptions()
    subscriptions.value = response.subscriptions
    activeCount.value = response.active_count
    mrrCents.value = response.mrr_cents
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Erreur lors du chargement des abonnements.')
  } finally {
    isLoading.value = false
  }
}

/**
 * Open the subscription detail drawer on the persistent stack.
 * @param subscription - The subscription to display.
 */
function openDrawer(subscription: AssistantSubscription): void {
  drawerStack.push({ kind: 'assistant-subscription', subscription })
}

/** Apply the latest subscription mutation broadcast by the drawer to the list (and refresh the KPIs). */
function applySubscriptionMutation(): void {
  const notice: AssistantSubscriptionMutationNotice | null = drawerStack.lastSubscriptionMutation
  if (!notice) return
  const index: number = subscriptions.value.findIndex(
    (subscription: AssistantSubscription): boolean => subscription.id === notice.subscription.id,
  )
  if (index !== -1) subscriptions.value.splice(index, 1, notice.subscription)
  loadAll()
}

watch((): number => drawerStack.subscriptionMutationCounter, applySubscriptionMutation)

onMounted(async (): Promise<void> => {
  await loadAll()
})
</script>
