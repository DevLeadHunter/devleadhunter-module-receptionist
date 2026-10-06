<template>
  <form class="flex flex-col gap-6" @submit.prevent="save">
    <section v-show="isIdentityShown" class="flex flex-col gap-4">
      <h3 v-if="isEverythingShown" class="app-label !text-[0.6rem]">Identité</h3>
      <label class="flex flex-col gap-1">
        <span class="text-xs font-medium text-[var(--app-ink)]">Entreprise affichée</span>
        <input v-model="form.business_name" type="text" class="app-input" maxlength="255" required />
      </label>
      <div class="flex flex-col gap-1.5">
        <span class="text-xs font-medium text-[var(--app-ink)]">Réceptionniste</span>
        <AssistantPersonaPicker
          v-model="form.assistant_name"
          v-model:custom-image-picked="form.avatar_enabled"
          :demo-url="props.assistant.demo_url"
          :accent-color="form.accent_color || null"
          :custom-image-url="props.assistant.avatar_url"
          :custom-image-background="props.assistant.avatar_is_transparent ? props.assistant.avatar_background : null"
          @customize="isAvatarModalOpen = true"
        />
        <AssistantAvatarModal
          :open="isAvatarModalOpen"
          :assistant="props.assistant"
          :accent-color="form.accent_color || null"
          @close="isAvatarModalOpen = false"
          @updated="onAvatarUpdated"
        />
      </div>
      <label class="flex flex-col gap-1">
        <span class="text-xs font-medium text-[var(--app-ink)]">Prénom affiché</span>
        <input v-model="form.assistant_name" type="text" class="app-input" maxlength="64" placeholder="Sofia" />
        <span class="text-[11px] text-[var(--app-ink-soft)]">
          Un autre prénom garde le visage de l'un des six, selon son genre.
        </span>
      </label>
      <div class="flex flex-col gap-1.5">
        <span class="text-xs font-medium text-[var(--app-ink)]">Ton</span>
        <UiChipToggleGroup v-model="toneWords" :options="toneOptions" label="Ton" />
        <span class="text-[11px] text-[var(--app-ink-soft)]">{{ toneSummary }}</span>
      </div>
      <div class="flex flex-col gap-1.5">
        <span class="text-xs font-medium text-[var(--app-ink)]">Langues proposées</span>
        <UiChipToggleGroup v-model="form.languages" :options="LANGUAGE_OPTIONS" label="Langues proposées" />
        <p v-if="form.languages.length === 0" class="text-xs text-[var(--app-red)]">Choisissez au moins une langue.</p>
      </div>
      <div class="flex items-center justify-between gap-3">
        <span class="text-xs font-medium text-[var(--app-ink)]">Couleur d'accent</span>
        <div class="flex items-center gap-2">
          <input
            v-model="form.accent_color"
            type="color"
            class="h-10 w-12 cursor-pointer rounded border border-[var(--app-line)] bg-transparent"
            aria-label="Choisir la couleur d'accent"
          />
          <input
            v-model="form.accent_color"
            type="text"
            class="app-input w-28"
            maxlength="32"
            placeholder="#c8862f"
            aria-label="Couleur d'accent en hexadécimal"
          />
        </div>
      </div>
    </section>

    <section
      v-show="isAlertsShown"
      :class="['flex flex-col gap-4', isEverythingShown ? 'border-t border-[var(--app-line-soft)] pt-5' : '']"
    >
      <div class="flex flex-col gap-1">
        <h3 v-if="isEverythingShown" class="app-label !text-[0.6rem]">Alertes au commerçant</h3>
        <p class="text-muted text-xs leading-relaxed">
          Une fois l'assistant vendu : chaque demande par email, et un SMS pour celles qui ne peuvent pas attendre.
          Rappel le lendemain si elle n'est pas traitée.
        </p>
      </div>
      <label class="flex flex-col gap-1">
        <span class="text-xs font-medium text-[var(--app-ink)]">Email du commerçant</span>
        <input
          v-model="form.email"
          type="email"
          inputmode="email"
          autocomplete="off"
          class="app-input"
          maxlength="255"
          placeholder="contact@entreprise.fr"
        />
        <span class="text-muted text-xs leading-relaxed">
          Reçoit les demandes, le rapport mensuel et le lien de l'espace client.
        </span>
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-xs font-medium text-[var(--app-ink)]">Mobile du commerçant</span>
        <input
          v-model="form.alert_phone"
          type="tel"
          inputmode="tel"
          autocomplete="off"
          class="app-input"
          maxlength="32"
          placeholder="06 12 34 56 78 ou +352 621 123 456"
        />
      </label>

      <div class="flex flex-col gap-4 rounded-lg border border-[var(--app-line-soft)] bg-[var(--app-surface-2)] p-4">
        <UiSwitch id="assistant-alert-sms" v-model="form.alert_sms_enabled" label="SMS immédiat" />
        <template v-if="form.alert_sms_enabled">
          <p v-if="form.alert_phone.trim() === ''" class="text-muted text-xs leading-relaxed">
            Sans mobile, aucun SMS ne part : seul l'email de résumé est envoyé.
          </p>
          <div class="flex flex-col gap-2">
            <span class="text-xs font-medium text-[var(--app-ink)]">Pour quelles demandes</span>
            <UiChipToggleGroup v-model="form.alert_sms_types" :options="ALERT_TYPE_OPTIONS" label="SMS immédiat pour" />
          </div>
          <div class="flex flex-col gap-2">
            <span class="text-xs font-medium text-[var(--app-ink)]">Ne pas déranger</span>
            <div class="flex items-center gap-2 text-xs text-[var(--app-ink-soft)]">
              <span>de</span>
              <div class="w-24">
                <UiSelectField v-model="form.alert_quiet_start_hour" :options="HOUR_OPTIONS" />
              </div>
              <span>à</span>
              <div class="w-24">
                <UiSelectField v-model="form.alert_quiet_end_hour" :options="HOUR_OPTIONS" />
              </div>
            </div>
            <span class="text-muted text-xs leading-relaxed">Les SMS reçus dans la plage partent à sa fin.</span>
          </div>
        </template>
      </div>

      <div class="rounded-lg border border-[var(--app-line-soft)] bg-[var(--app-surface-2)] p-4">
        <UiSwitch
          id="assistant-alert-email"
          v-model="form.alert_email_enabled"
          label="Email de résumé (toutes les demandes)"
        />
      </div>
    </section>

    <section v-show="isAlertsShown" class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-5">
      <h3 class="app-label !text-[0.6rem]">Boîte mail Gmail (bêta)</h3>
      <UiSwitch id="assistant-mailbox" v-model="form.mailbox_enabled" label="Préparer les réponses aux emails" />
      <p class="text-muted text-xs leading-relaxed">
        Le client connecte son Gmail depuis son espace : chaque email d'un client y reçoit une réponse en brouillon,
        qu'il relit puis envoie. Tant que Google n'a pas validé l'application, seuls les comptes déclarés comme testeurs
        dans la console Google peuvent se connecter. Désactiver déconnecte sa boîte.
      </p>
    </section>

    <section v-show="isAlertsShown" class="flex flex-col gap-2 border-t border-[var(--app-line-soft)] pt-5">
      <h3 class="app-label !text-[0.6rem]">Modèle</h3>
      <UiSwitch id="assistant-eu-only" v-model="form.eu_only" label="IA hébergée en Europe (Mistral)" />
      <p class="text-muted text-xs leading-relaxed">
        Les échanges de cet assistant ne partent jamais chez un autre fournisseur, même en cas de panne de Mistral
        (l'assistant propose alors de laisser ses coordonnées).
      </p>
    </section>

    <div v-if="isEverythingShown" class="flex flex-col gap-2 border-t border-[var(--app-line)] pt-4">
      <button
        type="submit"
        class="btn-primary w-full disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="isSaving || form.languages.length === 0"
      >
        <UIcon v-if="isSaving" name="i-lucide-loader-circle" class="mr-1.5 h-4 w-4 animate-spin" />
        Enregistrer
      </button>
      <p class="text-muted text-center text-[11px] leading-relaxed">
        La démo, le widget installé et l'espace client changent aussitôt ; l'aperçu ci-contre se recharge.
      </p>
    </div>
  </form>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import type {
  AiAssistantAlertSettings,
  AiAssistantEditForm,
  AiAssistantRequestType,
  AiAssistantSummary,
  AiAssistantUpdatePayload,
} from '~/types/AiAssistant'
import type {
  AssistantSettingsFormChangedSections,
  AssistantSettingsFormEmits,
  AssistantSettingsFormProps,
  AssistantSettingsFormSection,
} from '~/types/AssistantSettingsForm'
import type { UseToastReturn } from '~/types/Composables'
import type { SelectFieldOption } from '~/types/SelectField'
import { computed, ref, watch } from 'vue'
import AssistantAvatarModal from '~/components/ai-assistants/AssistantAvatarModal.vue'
import AssistantPersonaPicker from '~/components/ai-assistants/AssistantPersonaPicker.vue'
import { useToast } from '~/composables/useToast'
import { ASSISTANT_TONE_OPTIONS } from '~/constants/assistantTones'
import { AiAssistantService } from '~/services/aiAssistantService'
import { widgetLanguageCode } from '~/utils/aiAssistantLabels'
import { formatAssistantTone, parseAssistantTone } from '~/utils/assistantTone'
import { withRecordChanges } from '~/utils/formSync'

/**
 * The form editing a receptionist: her identity (name, face, tone, languages, accent), the alerts her business
 * receives, the Gmail mailbox and the model. `section` shows one part alone, without the submit button: the page
 * then saves through the exposed `save()` and follows `hasChanges`.
 */
const props: AssistantSettingsFormProps = defineProps({
  assistant: {
    type: Object as PropType<AiAssistantSummary>,
    required: true,
  },
  section: {
    type: String as PropType<AssistantSettingsFormSection>,
    default: 'all',
  },
})

const emit: EmitFn<AssistantSettingsFormEmits> = defineEmits<AssistantSettingsFormEmits>()

const toast: UseToastReturn = useToast()

/** Starts of the API refusals worth showing as they are. */
const SAVE_REFUSALS: string[] = ["Numéro d'alerte", 'Adresse email', '« IA hébergée en Europe »', 'Boîte mail Gmail']

/** Request types the owner can have texted at once, the ones that cannot wait first. */
const ALERT_TYPE_OPTIONS: SelectFieldOption<AiAssistantRequestType>[] = [
  { value: 'quote', label: 'Devis' },
  { value: 'appointment', label: 'Rendez-vous' },
  { value: 'urgent', label: 'Urgence' },
  { value: 'question', label: 'Question' },
  { value: 'other', label: 'Autre' },
]

/** Whole hours of the day, for the quiet window. */
const HOUR_OPTIONS: SelectFieldOption<number>[] = Array.from(
  { length: 24 },
  (_: unknown, hour: number): SelectFieldOption<number> => ({ value: hour, label: `${hour} h` }),
)

/** The widget's languages: the only ones an assistant can offer. */
const LANGUAGE_OPTIONS: SelectFieldOption<string>[] = [
  { value: 'fr', label: 'Français' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'lb', label: 'Lëtzebuergesch' },
]

/** The fields of the identity section; every other field belongs to the alerts section. */
const IDENTITY_FIELDS: (keyof AiAssistantEditForm)[] = [
  'assistant_name',
  'business_name',
  'tone',
  'accent_color',
  'avatar_enabled',
  'languages',
]

const form: Ref<AiAssistantEditForm> = ref(formOf(props.assistant))
/** The tone as chips; the stored sentence is written from them on save. */
const toneWords: Ref<string[]> = ref(parseAssistantTone(props.assistant.tone))
const isSaving: Ref<boolean> = ref(false)
const isAvatarModalOpen: Ref<boolean> = ref(false)

const isEverythingShown: ComputedRef<boolean> = computed((): boolean => props.section === 'all')

const isIdentityShown: ComputedRef<boolean> = computed((): boolean => props.section !== 'alerts')

const isAlertsShown: ComputedRef<boolean> = computed((): boolean => props.section !== 'identity')

/** The tone chips: the known tones, plus any word of the stored tone that is not one of them (nothing is lost). */
const toneOptions: ComputedRef<SelectFieldOption<string>[]> = computed((): SelectFieldOption<string>[] => {
  const known: Set<string> = new Set(
    ASSISTANT_TONE_OPTIONS.map((option: SelectFieldOption<string>): string => option.value),
  )
  const extra: SelectFieldOption<string>[] = parseAssistantTone(props.assistant.tone)
    .filter((word: string): boolean => !known.has(word))
    .map((word: string): SelectFieldOption<string> => ({ value: word, label: word }))
  return [...ASSISTANT_TONE_OPTIONS, ...extra]
})

/** What the assistant will be told: « Ton : chaleureux, professionnel et concis. » */
const toneSummary: ComputedRef<string> = computed((): string => {
  const sentence: string = formatAssistantTone(toneWords.value)
  return sentence ? `Ton : ${sentence}.` : 'Aucun ton imposé : professionnel et chaleureux par défaut.'
})

/** The form as it stands, the tone sentence written from its chips. */
const draft: ComputedRef<AiAssistantEditForm> = computed(
  (): AiAssistantEditForm => ({ ...form.value, tone: formatAssistantTone(toneWords.value) }),
)

/** The form as the assistant is saved, to tell an edit from a refresh. */
const savedForm: ComputedRef<AiAssistantEditForm> = computed(
  (): AiAssistantEditForm => ({
    ...formOf(props.assistant),
    tone: formatAssistantTone(parseAssistantTone(props.assistant.tone)),
  }),
)

/** Which sections differ from the saved assistant. */
const changedSections: ComputedRef<AssistantSettingsFormChangedSections> = computed(
  (): AssistantSettingsFormChangedSections => {
    const changedFields: (keyof AiAssistantEditForm)[] = (
      Object.keys(draft.value) as (keyof AiAssistantEditForm)[]
    ).filter(
      (field: keyof AiAssistantEditForm): boolean =>
        JSON.stringify(draft.value[field]) !== JSON.stringify(savedForm.value[field]),
    )
    return {
      identity: changedFields.some((field: keyof AiAssistantEditForm): boolean => IDENTITY_FIELDS.includes(field)),
      alerts: changedFields.some((field: keyof AiAssistantEditForm): boolean => !IDENTITY_FIELDS.includes(field)),
    }
  },
)

/** Any unsaved edit, in either section. */
const hasChanges: ComputedRef<boolean> = computed(
  (): boolean => changedSections.value.identity || changedSections.value.alerts,
)

/**
 * The assistant's languages among the widget's, a stored « lu » read as « lb », without duplicates.
 * @param languages - The codes as stored on the assistant.
 * @returns The codes the language chips can show.
 */
function offeredLanguagesOf(languages: string[]): string[] {
  const offeredCodes: string[] = LANGUAGE_OPTIONS.map((option: SelectFieldOption<string>): string => option.value)
  const widgetCodes: string[] = languages.map(widgetLanguageCode)
  return [...new Set(widgetCodes)].filter((code: string): boolean => offeredCodes.includes(code))
}

/**
 * The form as the assistant is now.
 * @param assistant - The assistant to edit.
 * @returns The prefilled form.
 */
function formOf(assistant: AiAssistantSummary): AiAssistantEditForm {
  return {
    assistant_name: assistant.assistant_name,
    business_name: assistant.business_name,
    tone: assistant.tone ?? '',
    accent_color: assistant.accent_color ?? '',
    avatar_enabled: assistant.avatar_enabled,
    languages: offeredLanguagesOf(assistant.languages),
    email: assistant.email ?? '',
    alert_phone: assistant.alerts.phone ?? '',
    alert_sms_enabled: assistant.alerts.sms_enabled,
    alert_email_enabled: assistant.alerts.email_enabled,
    alert_sms_types: [...assistant.alerts.sms_types],
    alert_quiet_start_hour: assistant.alerts.quiet_start_hour,
    alert_quiet_end_hour: assistant.alerts.quiet_end_hour,
    eu_only: assistant.eu_only,
    mailbox_enabled: assistant.mailbox_enabled,
  }
}

/**
 * The alert settings the form changed, so an untouched setting keeps following the API default.
 * @param alerts - The assistant's current alert settings.
 * @param edited - The edited form.
 * @returns Only the alert fields that differ from the current settings.
 */
function changedAlertFields(alerts: AiAssistantAlertSettings, edited: AiAssistantEditForm): AiAssistantUpdatePayload {
  const changes: AiAssistantUpdatePayload = {}
  if (edited.alert_phone.trim() !== (alerts.phone ?? '')) changes.alert_phone = edited.alert_phone.trim()
  if (edited.alert_sms_enabled !== alerts.sms_enabled) changes.alert_sms_enabled = edited.alert_sms_enabled
  if (edited.alert_email_enabled !== alerts.email_enabled) changes.alert_email_enabled = edited.alert_email_enabled
  const sameTypes: boolean =
    edited.alert_sms_types.length === alerts.sms_types.length &&
    edited.alert_sms_types.every((type: AiAssistantRequestType): boolean => alerts.sms_types.includes(type))
  if (!sameTypes) changes.alert_sms_types = edited.alert_sms_types
  if (edited.alert_quiet_start_hour !== alerts.quiet_start_hour) {
    changes.alert_quiet_start_hour = edited.alert_quiet_start_hour
  }
  if (edited.alert_quiet_end_hour !== alerts.quiet_end_hour) changes.alert_quiet_end_hour = edited.alert_quiet_end_hour
  return changes
}

/**
 * Persist the customization; the page refreshes what shows the assistant, preview included.
 * @returns A promise resolved once saved or refused.
 */
async function save(): Promise<void> {
  const target: AiAssistantSummary = props.assistant
  if (isSaving.value) return
  if (form.value.languages.length === 0) {
    toast.error('Choisissez au moins une langue.')
    return
  }
  isSaving.value = true
  try {
    const payload: AiAssistantUpdatePayload = {
      assistant_name: form.value.assistant_name,
      business_name: form.value.business_name,
      tone: formatAssistantTone(toneWords.value),
      accent_color: form.value.accent_color,
      languages: form.value.languages,
      ...(form.value.email.trim() !== (target.email ?? '') ? { email: form.value.email.trim() } : {}),
      ...changedAlertFields(target.alerts, form.value),
      ...(form.value.eu_only !== target.eu_only ? { eu_only: form.value.eu_only } : {}),
      ...(form.value.mailbox_enabled !== target.mailbox_enabled ? { mailbox_enabled: form.value.mailbox_enabled } : {}),
      ...(form.value.avatar_enabled !== target.avatar_enabled ? { avatar_enabled: form.value.avatar_enabled } : {}),
    }
    const updated: AiAssistantSummary = await AiAssistantService.update(target.id, payload)
    form.value = formOf(updated)
    toneWords.value = parseAssistantTone(updated.tone)
    toast.success('Réceptionniste personnalisée.')
    emit('saved', updated)
  } catch (error: unknown) {
    // The API explains what it refused (alert number, email, Europe-hosted AI without Mistral, Gmail); anything else stays generic.
    const detail: string = error instanceof Error ? error.message : ''
    const explained: boolean = SAVE_REFUSALS.some((prefix: string): boolean => detail.startsWith(prefix))
    toast.error(explained ? detail : 'Enregistrement impossible pour le moment.')
  } finally {
    isSaving.value = false
  }
}

/**
 * Drop every unsaved edit: the form goes back to the assistant as it is saved.
 */
function reset(): void {
  form.value = formOf(props.assistant)
  toneWords.value = parseAssistantTone(props.assistant.tone)
}

/**
 * The image was sent, chosen or deleted in its dialog: the card follows at once, whatever was picked before.
 * @param updated - The assistant as the API returned it.
 */
function onAvatarUpdated(updated: AiAssistantSummary): void {
  form.value.avatar_enabled = updated.avatar_enabled
  emit('saved', updated)
}

watch(
  (): AiAssistantSummary => props.assistant,
  (assistant: AiAssistantSummary, previous: AiAssistantSummary): void => {
    if (assistant.id !== previous.id) {
      form.value = formOf(assistant)
      toneWords.value = parseAssistantTone(assistant.tone)
      return
    }
    // The same receptionist refreshed (its image, the video status): the server's changes come in, the edits stay.
    form.value = withRecordChanges(form.value, formOf(previous), formOf(assistant))
    if (assistant.tone !== previous.tone) toneWords.value = parseAssistantTone(assistant.tone)
  },
)

watch(
  draft,
  (edited: AiAssistantEditForm): void => {
    emit('draft', edited)
  },
  { deep: true },
)

defineExpose({ hasChanges, changedSections, isSaving, save, reset })
</script>
