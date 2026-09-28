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
        <UiCopyLinkField
          v-if="linkToCopy"
          :url="linkToCopy.url"
          :label="`Lien d'abonnement ${intervalLabel(linkToCopy.interval)}`"
        />
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
import type {
  AiAssistantSubscriptionLink,
  AiAssistantSummary,
  AssistantSubscriptionInterval,
} from '~/types/AiAssistant'
import type { AssistantSubscriptionCardProps, AssistantSubscriptionLinkToCopy } from '~/types/AssistantSubscriptionCard'
import type { UseToastReturn } from '~/types/Composables'
import { computed, ref } from 'vue'
import { AiAssistantService } from '~/services/aiAssistantService'
import { useToast } from '~/composables/useToast'
import { ClipboardCopy } from '~/utils/clipboardCopy'

const props: AssistantSubscriptionCardProps = defineProps({
  assistant: {
    type: Object as PropType<AiAssistantSummary>,
    required: true,
  },
})

const toast: UseToastReturn = useToast()

const isCopyingLink: Ref<boolean> = ref(false)
/** The link the browser refused to copy, shown in a field with its own copy button. */
const linkToCopy: Ref<AssistantSubscriptionLinkToCopy | null> = ref(null)

const subscriptionLabel: ComputedRef<string> = computed((): string => {
  if (props.assistant.subscription_amount_cents == null) return ''
  const euros: number = Math.round(props.assistant.subscription_amount_cents / 100)
  return `${euros} €/${props.assistant.subscription_interval === 'year' ? 'an' : 'mois'}`
})

/**
 * The billing period as the link's label names it.
 * @param interval - `month` or `year`.
 * @returns « mensuel » or « annuel ».
 */
function intervalLabel(interval: AssistantSubscriptionInterval): string {
  return interval === 'year' ? 'annuel' : 'mensuel'
}

/**
 * Copy the permanent subscription link, asked for and written from the click itself so Safari allows the copy.
 * @param interval - `month` or `year`.
 * @returns A promise resolved once the link is copied, or shown to copy by hand.
 */
async function copySubscriptionLink(interval: AssistantSubscriptionInterval): Promise<void> {
  if (isCopyingLink.value) return
  isCopyingLink.value = true
  linkToCopy.value = null
  const linkRequest: Promise<string> = AiAssistantService.getSubscriptionLink(props.assistant.id, interval).then(
    (link: AiAssistantSubscriptionLink): string => link.url,
  )
  const copyAttempt: Promise<boolean> = ClipboardCopy.copyWhenReady(linkRequest)
  try {
    const url: string = await linkRequest
    if (await copyAttempt) {
      toast.success(`Lien d'abonnement ${intervalLabel(interval)} copié.`)
    } else {
      linkToCopy.value = { interval, url }
    }
  } catch {
    toast.error('Lien indisponible pour cet assistant.')
  } finally {
    isCopyingLink.value = false
  }
}
</script>
