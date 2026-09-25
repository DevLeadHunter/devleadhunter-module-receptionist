<template>
  <div class="rounded-xl border border-[var(--app-line)] bg-[var(--app-bg)] p-4">
    <div class="flex items-center justify-between gap-3">
      <h3 class="text-sm font-semibold text-[var(--app-ink)]">Abonnement</h3>
      <span v-if="props.assistant.subscription_status === 'active'" class="app-badge app-badge--success">
        Abonné · {{ subscriptionLabel }}
      </span>
    </div>
    <template v-if="props.assistant.status !== 'delivered'">
      <p class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]">
        Le lien ouvre un paiement Stripe à chaque clic et reste valable : envoyez-le au client quand il dit oui.
      </p>
      <div class="mt-3 space-y-2">
        <button
          type="button"
          class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="isCopyingLink"
          @click="copySubscriptionLink('month')"
        >
          <UIcon name="i-lucide-link" class="mr-1.5 h-3.5 w-3.5" />
          Copier le lien mensuel
        </button>
        <button
          type="button"
          class="btn-secondary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="isCopyingLink"
          @click="copySubscriptionLink('year')"
        >
          <UIcon name="i-lucide-link" class="mr-1.5 h-3.5 w-3.5" />
          Copier le lien annuel
        </button>
      </div>
    </template>
    <p
      v-else-if="props.assistant.subscription_status !== 'active'"
      class="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]"
    >
      Vendu sans abonnement Stripe enregistré.
    </p>
    <NuxtLink
      v-else
      to="/dashboard/subscriptions"
      class="mt-2 block text-xs text-[var(--app-ink-soft)] underline underline-offset-2 hover:text-[var(--app-ink)]"
    >
      Voir dans Abonnements
    </NuxtLink>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AiAssistantSummary } from '~/types/AiAssistant'
import type { AssistantSubscriptionCardProps, AssistantSubscriptionInterval } from '~/types/AssistantSubscriptionCard'
import type { UseCopyToClipboardReturn, UseToastReturn } from '~/types/Composables'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useToast } from '~/composables/useToast'

const props: AssistantSubscriptionCardProps = defineProps({
  assistant: {
    type: Object as PropType<AiAssistantSummary>,
    required: true,
  },
})

const toast: UseToastReturn = useToast()
const { copy }: UseCopyToClipboardReturn = useCopyToClipboard()

const isCopyingLink: Ref<boolean> = ref(false)

const subscriptionLabel: ComputedRef<string> = computed((): string => {
  if (props.assistant.subscription_amount_cents == null) return ''
  const euros: number = Math.round(props.assistant.subscription_amount_cents / 100)
  return `${euros} €/${props.assistant.subscription_interval === 'year' ? 'an' : 'mois'}`
})

/**
 * Copy the permanent subscription link for the client.
 * @param interval - `month` or `year`.
 * @returns A promise resolved once copied.
 */
async function copySubscriptionLink(interval: AssistantSubscriptionInterval): Promise<void> {
  if (isCopyingLink.value) return
  isCopyingLink.value = true
  try {
    const { url }: { url: string } = await AiAssistantService.getSubscriptionLink(props.assistant.id, interval)
    await copy(url)
    toast.success(`Lien d'abonnement ${interval === 'year' ? 'annuel' : 'mensuel'} copié.`)
  } catch {
    toast.error('Lien indisponible pour cet assistant.')
  } finally {
    isCopyingLink.value = false
  }
}
</script>
