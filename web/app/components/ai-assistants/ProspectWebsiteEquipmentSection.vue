<template>
  <div class="space-y-3 px-5 py-4">
    <div class="flex items-center justify-between gap-3">
      <p class="text-[10px] font-semibold tracking-wider text-[var(--app-ink-soft)] uppercase">Équipement du site</p>
      <button
        type="button"
        class="btn-secondary text-xs"
        :disabled="isScanningEquipment"
        @click="handleWebsiteEquipmentScan"
      >
        <UIcon
          :name="isScanningEquipment ? 'i-lucide-loader-circle' : 'i-lucide-scan-search'"
          :class="['h-3.5 w-3.5', isScanningEquipment && 'animate-spin']"
        />
        {{ isScanningEquipment ? 'Analyse…' : prospect.website_equipment_json ? 'Relancer' : 'Analyser' }}
      </button>
    </div>

    <template v-if="prospect.website_equipment_json">
      <div class="flex flex-wrap gap-1.5">
        <span v-if="ProspectWebsite.isChatEquipped(prospect)" class="app-badge app-badge--engaged">
          <UIcon name="i-lucide-message-circle" class="h-3 w-3" />
          Chat : {{ ProspectWebsite.chatProviderLabels(prospect).join(', ') }}
        </span>
        <span v-else class="app-badge app-badge--success">
          <UIcon name="i-lucide-message-circle-off" class="h-3 w-3" />
          Aucun chat
        </span>
        <span class="app-badge">
          <UIcon
            :name="prospect.website_equipment_json.has_contact_form ? 'i-lucide-mail' : 'i-lucide-mail-x'"
            class="h-3 w-3"
          />
          {{ prospect.website_equipment_json.has_contact_form ? 'Formulaire de contact' : 'Pas de formulaire' }}
        </span>
      </div>
      <p class="text-xs leading-relaxed text-[var(--app-ink-soft)]">{{ websiteEquipmentAdvice }}</p>
      <p v-if="prospect.website_equipment_at" class="text-[10px] text-[var(--app-faint)]">
        Analysé le {{ formatLongMonthDate(prospect.website_equipment_at) }}
      </p>
    </template>

    <p v-else class="text-xs leading-relaxed text-[var(--app-ink-soft)]">
      Détecte un chat déjà installé (Tidio, Crisp, IONOS…) et un formulaire de contact.
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import type { Prospect } from '~/types'
import type { UseToastReturn } from '~/types/Composables'
import type {
  ProspectWebsiteEquipmentSectionEmits,
  ProspectWebsiteEquipmentSectionProps,
} from '../../types/ProspectWebsiteEquipmentSection'
import { computed, ref } from 'vue'
import { useToast } from '~/composables/useToast'
import { ProspectsService } from '~/services/prospectsService'
import { formatLongMonthDate } from '~/utils/date'
import { ProspectWebsite } from '~/utils/prospectWebsite'

const props: ProspectWebsiteEquipmentSectionProps = defineProps({
  prospect: {
    type: Object as PropType<Prospect>,
    required: true,
  },
  openingId: {
    type: Number,
    required: true,
  },
})

const emit: EmitFn<ProspectWebsiteEquipmentSectionEmits> = defineEmits<ProspectWebsiteEquipmentSectionEmits>()

const toast: UseToastReturn = useToast()

const isScanningEquipment: Ref<boolean> = ref(false)

/** What the last website scan means for the Réceptionniste IA pitch. */
const websiteEquipmentAdvice: ComputedRef<string> = computed((): string =>
  ProspectWebsite.isChatEquipped(props.prospect)
    ? "Déjà équipé d'un chat : parlez de ce qu'il ne fait pas (photo, SMS au patron, rapport mensuel) ou passez au suivant."
    : "Aucun chat : ses demandes écrites attendent qu'il rappelle, la réceptionniste a sa place.",
)

/**
 * Scan the prospect's website for a chat widget and a contact form (a few seconds).
 * @returns A promise resolved once the scan is stored.
 */
async function handleWebsiteEquipmentScan(): Promise<void> {
  isScanningEquipment.value = true
  try {
    const updated: Prospect = await ProspectsService.scanWebsiteEquipment(props.prospect.id)
    emit('updated', updated)
    toast.success(ProspectWebsite.isChatEquipped(updated) ? 'Chat déjà installé sur ce site' : 'Aucun chat sur ce site')
  } catch (err: unknown) {
    toast.error(err instanceof Error ? err.message : "L'analyse du site a échoué")
  } finally {
    isScanningEquipment.value = false
  }
}
</script>
