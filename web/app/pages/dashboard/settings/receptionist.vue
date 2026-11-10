<template>
  <div class="max-w-3xl space-y-5">
    <UiPageHeader
      eyebrow="Compte"
      title="Réceptionniste IA"
      description="Le prix de l'abonnement que vous vendez avec la réceptionniste."
    />

    <section>
      <div class="app-card p-5">
        <div class="flex items-start gap-3">
          <span
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)]"
          >
            <UIcon name="i-lucide-bot" class="h-4 w-4 text-[var(--app-ink-soft)]" />
          </span>
          <div>
            <h2 class="text-sm font-semibold text-[var(--app-ink)]">Abonnement Réceptionniste IA</h2>
            <p class="mt-0.5 text-xs text-[var(--app-ink-soft)]">
              Le prix mensuel de l'assistant et les mois offerts sur l'annuel, affichés via
              <code class="rounded bg-[var(--app-surface-2)] px-1 py-0.5 text-[0.7rem]">{prix_assistant}</code> et sur
              la page de démo. Conseillé : 79 à 99 €/mois. Les abonnés en cours gardent leur prix — seuls les nouveaux
              paient le nouveau tarif.
            </p>
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-end gap-3 border-t border-[var(--app-line-soft)] pt-4">
          <label class="min-w-[9rem] flex-1">
            <span class="mb-1 block text-xs font-medium text-[var(--app-ink-soft)]">Prix mensuel (€)</span>
            <input
              v-model.number="assistantMonthlyEuros"
              type="number"
              min="0"
              step="1"
              class="app-input w-full"
              :disabled="!hasLoadedPricing"
              @keydown.enter="saveAssistantPrice"
            />
          </label>
          <label class="min-w-[9rem] flex-1">
            <span class="mb-1 block text-xs font-medium text-[var(--app-ink-soft)]">Mois offerts (annuel)</span>
            <input
              v-model.number="assistantFreeMonths"
              type="number"
              min="0"
              max="11"
              step="1"
              class="app-input w-full"
              :disabled="!hasLoadedPricing"
              @keydown.enter="saveAssistantPrice"
            />
          </label>
          <button
            type="button"
            class="app-btn-primary h-9 px-4 text-xs"
            :disabled="!canSaveAssistant || isSavingAssistant"
            @click="saveAssistantPrice"
          >
            <UIcon v-if="isSavingAssistant" name="i-lucide-loader-circle" class="h-3.5 w-3.5 animate-spin" />
            Enregistrer
          </button>
        </div>

        <p class="mt-2 text-xs text-[var(--app-ink-soft)]">
          Annuel : <strong>{{ assistantAnnualEuros }} €/an</strong> ({{ assistantFreeMonths }} mois offerts).
        </p>
        <p
          v-if="assistantFeedback"
          class="mt-1 text-xs"
          :class="assistantFeedbackIsError ? 'text-[var(--app-red)]' : 'text-[var(--app-accent)]'"
        >
          {{ assistantFeedback }}
        </p>
      </div>
    </section>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { AssistantPricing } from '../../../types/AiAssistant'
import { computed, onMounted, ref } from 'vue'
import { AiAssistantService } from '../../../services/aiAssistantService'

definePageMeta({ layout: 'dashboard', middleware: ['auth', 'ai-assistant-module'] })

useSeoMeta({ title: 'Réceptionniste IA — DevLeadHunter' })

const DEFAULT_ASSISTANT_MONTHLY_CENTS: number = 7900
const DEFAULT_ASSISTANT_FREE_MONTHS: number = 2

const assistantMonthlyEuros: Ref<number> = ref(DEFAULT_ASSISTANT_MONTHLY_CENTS / 100)
const assistantFreeMonths: Ref<number> = ref(DEFAULT_ASSISTANT_FREE_MONTHS)
/** The saved price is shown: until then nothing can be saved, so a failed read never overwrites it. */
const hasLoadedPricing: Ref<boolean> = ref(false)
const isSavingAssistant: Ref<boolean> = ref(false)
const assistantFeedback: Ref<string> = ref('')
const assistantFeedbackIsError: Ref<boolean> = ref(false)

/** Annual price in euros: monthly × (12 - free months), at least one month billed. */
const assistantAnnualEuros: ComputedRef<number> = computed((): number => {
  const billedMonths: number = Math.max(1, 12 - (assistantFreeMonths.value || 0))
  return Math.round((assistantMonthlyEuros.value || 0) * billedMonths)
})

/** True when the price is loaded and both inputs are valid (price ≥ 0, free months an integer 0-11). */
const canSaveAssistant: ComputedRef<boolean> = computed(
  (): boolean =>
    hasLoadedPricing.value &&
    Number.isFinite(assistantMonthlyEuros.value) &&
    assistantMonthlyEuros.value >= 0 &&
    Number.isInteger(assistantFreeMonths.value) &&
    assistantFreeMonths.value >= 0 &&
    assistantFreeMonths.value <= 11,
)

/**
 * Show a price as the API holds it.
 * @param pricing - The monthly price in cents and the months offered on the annual plan.
 */
function applyPricing(pricing: AssistantPricing): void {
  assistantMonthlyEuros.value = pricing.monthly_price_cents / 100
  assistantFreeMonths.value = pricing.annual_free_months
}

/**
 * Read the saved subscription price.
 * @returns A promise resolved once it is shown, or the failure is.
 */
async function loadAssistantPrice(): Promise<void> {
  try {
    applyPricing(await AiAssistantService.getPricing())
    hasLoadedPricing.value = true
  } catch (err: unknown) {
    assistantFeedbackIsError.value = true
    assistantFeedback.value = err instanceof Error ? err.message : 'Le prix enregistré est illisible pour le moment.'
  }
}

/**
 * Persist the assistant subscription price and the annual free months.
 * @returns A promise resolved once saved, or the failure is shown.
 */
async function saveAssistantPrice(): Promise<void> {
  if (!canSaveAssistant.value || isSavingAssistant.value) {
    return
  }
  isSavingAssistant.value = true
  assistantFeedback.value = ''
  try {
    applyPricing(
      await AiAssistantService.updatePricing({
        monthly_price_cents: Math.round(assistantMonthlyEuros.value * 100),
        annual_free_months: assistantFreeMonths.value,
      }),
    )
    assistantFeedbackIsError.value = false
    assistantFeedback.value = 'Abonnement enregistré.'
  } catch (err: unknown) {
    assistantFeedbackIsError.value = true
    assistantFeedback.value = err instanceof Error ? err.message : "L'enregistrement a échoué."
  } finally {
    isSavingAssistant.value = false
  }
}

onMounted(async (): Promise<void> => {
  await loadAssistantPrice()
})
</script>
