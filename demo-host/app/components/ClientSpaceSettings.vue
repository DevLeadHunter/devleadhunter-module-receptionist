<template>
  <form class="cs-settings" @submit.prevent="submit">
    <!-- Frozen while a save is in flight: a value typed meanwhile would be overwritten by the answer. -->
    <fieldset class="cs-settings__fields" :disabled="props.isSaving || props.readOnly">
      <template v-if="props.part === 'assistant'">
        <p class="cs-sec">Prénom</p>
        <div class="cs-block cs-settings__block">
          <label class="cs-field">
            <span class="cs-label">Prénom affiché aux visiteurs</span>
            <input v-model="assistantName" class="cs-input" type="text" maxlength="64" required autocomplete="off" />
            <span class="cs-hint">Se présente toujours aux visiteurs comme réceptionniste IA de votre entreprise.</span>
          </label>
        </div>

        <p class="cs-sec">Langues proposées aux visiteurs</p>
        <div class="cs-block">
          <label
            v-for="option in props.languageOptions"
            :key="option.code"
            class="cs-cell cs-settings__choice"
            :class="{ 'cs-settings__choice--on': languages.includes(option.code) }"
          >
            <input
              type="checkbox"
              class="cs-settings__check"
              :checked="languages.includes(option.code)"
              @change="toggleLanguage(option.code)"
            />
            <span>{{ option.label }}</span>
            <ClientSpaceIcon v-if="languages.includes(option.code)" name="check" class="cs-settings__tick" />
          </label>
        </div>
      </template>

      <template v-else>
        <p class="cs-sec">Par SMS</p>
        <div class="cs-block cs-settings__block">
          <label class="cs-settings__switch">
            <span>
              <b>Alertes par SMS</b>
              <span>Tout de suite, pour les demandes qui ne peuvent pas attendre.</span>
            </span>
            <input v-model="smsEnabled" type="checkbox" />
          </label>
          <label class="cs-field">
            <span class="cs-label">Mobile qui reçoit les SMS</span>
            <input
              v-model="alertPhone"
              class="cs-input"
              type="tel"
              inputmode="tel"
              maxlength="32"
              placeholder="06 12 34 56 78 ou +352 621 123 456"
              autocomplete="tel"
            />
          </label>
          <div v-if="!props.readOnly" class="cs-settings__test">
            <button type="button" class="cs-btn cs-btn--small" :disabled="!canTestSms" @click="emit('test-sms')">
              {{ props.testSmsState === 'sending' ? 'Envoi…' : 'Envoyer un SMS test' }}
            </button>
            <span class="cs-hint" :class="{ 'cs-hint--error': props.testSmsState === 'failed' }">{{
              testSmsHint
            }}</span>
          </div>
          <template v-if="smsEnabled">
            <p class="cs-label">SMS immédiat pour</p>
            <div class="cs-settings__chips">
              <label
                v-for="option in CLIENT_SPACE_REQUEST_TYPE_OPTIONS"
                :key="option.value"
                class="cs-settings__chip"
                :class="{ 'cs-settings__chip--on': smsTypes.includes(option.value) }"
              >
                <input
                  type="checkbox"
                  class="cs-settings__check"
                  :checked="smsTypes.includes(option.value)"
                  @change="toggleSmsType(option.value)"
                />
                {{ option.label }}
              </label>
            </div>
            <span class="cs-hint">Les autres demandes arrivent par e-mail seulement.</span>
          </template>
        </div>

        <p class="cs-sec">Par e-mail</p>
        <div class="cs-block cs-settings__block">
          <label class="cs-settings__switch">
            <span>
              <b>Chaque demande par e-mail</b>
              <span>À l’adresse de votre entreprise, avec le message et les photos.</span>
            </span>
            <input v-model="emailEnabled" type="checkbox" />
          </label>
        </div>

        <template v-if="smsEnabled">
          <p class="cs-sec">Ne pas déranger</p>
          <div class="cs-block cs-settings__block">
            <div class="cs-settings__hours">
              <span>de</span>
              <select v-model.number="quietStartHour" class="cs-input cs-settings__hour" aria-label="Début de la plage">
                <option v-for="hour in HOURS" :key="hour" :value="hour">{{ hour }} h</option>
              </select>
              <span>à</span>
              <select v-model.number="quietEndHour" class="cs-input cs-settings__hour" aria-label="Fin de la plage">
                <option v-for="hour in HOURS" :key="hour" :value="hour">{{ hour }} h</option>
              </select>
            </div>
            <span class="cs-hint">Les SMS reçus dans la plage partent à sa fin. Mêmes heures : jamais retenus.</span>
          </div>
        </template>
      </template>
    </fieldset>

    <div v-if="!props.readOnly" class="cs-settings__foot">
      <ClientSpaceSaveBar
        :is-busy="props.isSaving"
        :can-save="canSave"
        :error-message="props.errorMessage"
        :show-saved="props.hasSaved && !hasChanges"
      />
    </div>
  </form>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AssistantWidgetLanguage } from '~/types/AiAssistant'
import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientRequestType,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
  AiAssistantClientTestSmsState,
} from '~/types/AiAssistantClientSpace'
import type {
  ClientSpaceSettingsEmits,
  ClientSpaceSettingsPart,
  ClientSpaceSettingsProps,
} from '~/types/ClientSpaceSettings'
import { CLIENT_SPACE_REQUEST_TYPE_OPTIONS } from '~/constants/ClientSpaceRequestTypes'

/** Whole hours of the day, for the quiet window. */
const HOURS: number[] = Array.from({ length: 24 }, (_: unknown, hour: number): number => hour)

/**
 * The settings a client changes alone, in two screens: the receptionist (her first name, her languages) and the
 * alerts (mobile, SMS and email switches, the request types texted at once, the quiet window).
 * @param part Which screen this form is.
 * @param settings The current settings, defaults applied.
 * @param languageOptions The languages the widget can speak.
 * @param isSaving A save is in flight.
 * @param errorMessage Why the last save was refused, if it was.
 * @param hasSaved The last save went through.
 * @param readOnly The example space: shown, never saved.
 * @param testSmsState Where the test SMS to the saved mobile stands.
 * @param testSmsMessage What the API said of the test SMS, if anything.
 */
const props: ClientSpaceSettingsProps = defineProps({
  part: { type: String as PropType<ClientSpaceSettingsPart>, required: true },
  settings: { type: Object as PropType<AiAssistantClientSettings>, required: true },
  languageOptions: { type: Array as PropType<AiAssistantClientLanguageOption[]>, required: true },
  isSaving: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  hasSaved: { type: Boolean, default: false },
  readOnly: { type: Boolean, default: false },
  testSmsState: { type: String as PropType<AiAssistantClientTestSmsState>, default: 'idle' },
  testSmsMessage: { type: String as PropType<string | null>, default: null },
})

const emit: EmitFn<ClientSpaceSettingsEmits> = defineEmits<ClientSpaceSettingsEmits>()

const assistantName: Ref<string> = ref(props.settings.assistant_name)
const languages: Ref<AssistantWidgetLanguage[]> = ref([...props.settings.languages])
const alertPhone: Ref<string> = ref(props.settings.alert_phone ?? '')
const smsEnabled: Ref<boolean> = ref(props.settings.alert_sms_enabled)
const emailEnabled: Ref<boolean> = ref(props.settings.alert_email_enabled)
const smsTypes: Ref<AiAssistantClientRequestType[]> = ref([...props.settings.alert_sms_types])
const quietStartHour: Ref<number> = ref(props.settings.alert_quiet_start_hour)
const quietEndHour: Ref<number> = ref(props.settings.alert_quiet_end_hour)

const changes: ComputedRef<AiAssistantClientSettingsUpdate> = computed((): AiAssistantClientSettingsUpdate => {
  const update: AiAssistantClientSettingsUpdate = {}
  if (props.part === 'assistant') {
    const name: string = assistantName.value.trim()
    if (name && name !== props.settings.assistant_name) update.assistant_name = name
    if ([...languages.value].sort().join() !== [...props.settings.languages].sort().join()) {
      update.languages = [...languages.value]
    }
    return update
  }
  if (alertPhone.value.trim() !== (props.settings.alert_phone ?? '')) update.alert_phone = alertPhone.value.trim()
  if (smsEnabled.value !== props.settings.alert_sms_enabled) update.alert_sms_enabled = smsEnabled.value
  if (emailEnabled.value !== props.settings.alert_email_enabled) update.alert_email_enabled = emailEnabled.value
  if ([...smsTypes.value].sort().join() !== [...props.settings.alert_sms_types].sort().join()) {
    update.alert_sms_types = [...smsTypes.value]
  }
  if (quietStartHour.value !== props.settings.alert_quiet_start_hour) {
    update.alert_quiet_start_hour = quietStartHour.value
  }
  if (quietEndHour.value !== props.settings.alert_quiet_end_hour) update.alert_quiet_end_hour = quietEndHour.value
  return update
})

const hasChanges: ComputedRef<boolean> = computed((): boolean => Object.keys(changes.value).length > 0)

/** The test goes to the saved mobile: not while the number typed differs from it, nor without one. */
const canTestSms: ComputedRef<boolean> = computed(
  (): boolean =>
    Boolean(props.settings.alert_phone) &&
    changes.value.alert_phone === undefined &&
    props.testSmsState !== 'sending' &&
    !props.isSaving,
)

const testSmsHint: ComputedRef<string> = computed((): string => {
  if (!props.settings.alert_phone) return 'Enregistrez d’abord votre mobile.'
  if (changes.value.alert_phone !== undefined) return 'Enregistrez le nouveau numéro avant le test.'
  if (props.testSmsState === 'sent') return props.testSmsMessage ?? 'SMS envoyé.'
  if (props.testSmsState === 'failed') return props.testSmsMessage ?? 'Envoi impossible pour le moment.'
  return 'Un SMS pour vérifier que vos alertes arrivent bien.'
})

// Languages set only by the operator (not offered here) stay on the server: an empty choice is refused only
// when the client emptied it.
const canSave: ComputedRef<boolean> = computed(
  (): boolean => hasChanges.value && (changes.value.languages === undefined || changes.value.languages.length > 0),
)

/**
 * Add or remove a language from the offer.
 * @param code The language toggled.
 */
function toggleLanguage(code: AssistantWidgetLanguage): void {
  languages.value = languages.value.includes(code)
    ? languages.value.filter((item: AssistantWidgetLanguage): boolean => item !== code)
    : [...languages.value, code]
}

/**
 * Add or remove a request type from the ones texted at once.
 * @param type The request type toggled.
 */
function toggleSmsType(type: AiAssistantClientRequestType): void {
  smsTypes.value = smsTypes.value.includes(type)
    ? smsTypes.value.filter((item: AiAssistantClientRequestType): boolean => item !== type)
    : [...smsTypes.value, type]
}

/** Send only the fields that changed. */
function submit(): void {
  if (!canSave.value) return
  emit('save', changes.value)
}

watch(
  (): AiAssistantClientSettings => props.settings,
  (saved: AiAssistantClientSettings): void => {
    assistantName.value = saved.assistant_name
    languages.value = [...saved.languages]
    alertPhone.value = saved.alert_phone ?? ''
    smsEnabled.value = saved.alert_sms_enabled
    emailEnabled.value = saved.alert_email_enabled
    smsTypes.value = [...saved.alert_sms_types]
    quietStartHour.value = saved.alert_quiet_start_hour
    quietEndHour.value = saved.alert_quiet_end_hour
  },
)
</script>

<style scoped>
.cs-settings__test {
  display: grid;
  gap: 6px;
  justify-items: start;
}

.cs-hint--error {
  color: var(--cs-red);
}

.cs-settings {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.cs-settings__fields {
  display: grid;
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}

.cs-settings__block {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.cs-settings__choice {
  cursor: pointer;
}

.cs-settings__choice--on {
  font-weight: 600;
}

.cs-settings__tick {
  color: var(--cs-accent-text);
}

.cs-settings__check {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.cs-settings__switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  cursor: pointer;
}

.cs-settings__switch > span {
  display: grid;
  gap: 2px;
  line-height: 1.35;
}

.cs-settings__switch b {
  font-size: 15.5px;
  font-weight: 600;
}

.cs-settings__switch > span > span {
  font-size: 13px;
  color: var(--cs-dim);
}

.cs-settings__switch input {
  flex: none;
  width: 22px;
  height: 22px;
  margin: 0;
  accent-color: var(--cs-accent-strong);
}

.cs-settings__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cs-settings__chip {
  cursor: pointer;
  border: 1px solid var(--cs-line);
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 14px;
  background: var(--cs-card);
}

.cs-settings__chip--on {
  border-color: var(--cs-accent-strong);
  background: var(--cs-accent-tint);
  color: var(--cs-accent-text);
  font-weight: 600;
}

.cs-settings__hours {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
}

.cs-settings__hour {
  width: auto;
}

.cs-settings__foot {
  padding: 18px 16px 24px;
}
</style>
