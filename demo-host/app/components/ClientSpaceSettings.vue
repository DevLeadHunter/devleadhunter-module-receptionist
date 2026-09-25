<template>
  <ClientSpaceSection title="Réglages">
    <form class="css__form" @submit.prevent="submit">
      <!-- Frozen while a save is in flight: a value typed meanwhile would be overwritten by the answer. -->
      <fieldset class="css__fields" :disabled="props.isSaving">
        <label class="cs-field">
          <span class="cs-label">Prénom affiché aux visiteurs</span>
          <input v-model="assistantName" class="cs-input" type="text" maxlength="64" required autocomplete="off" />
        </label>

        <fieldset class="cs-field">
          <legend class="cs-label">Langues proposées aux visiteurs</legend>
          <div class="css__chips">
            <label
              v-for="option in languageOptions"
              :key="option.code"
              class="css__chip"
              :class="{ 'css__chip--on': languages.includes(option.code) }"
            >
              <input
                type="checkbox"
                class="css__check"
                :checked="languages.includes(option.code)"
                @change="toggleLanguage(option.code)"
              />
              {{ option.label }}
            </label>
          </div>
        </fieldset>

        <label class="cs-field">
          <span class="cs-label">Mobile qui reçoit les alertes SMS</span>
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

        <div class="css__toggles">
          <label class="css__toggle">
            <input v-model="smsEnabled" type="checkbox" />
            Alertes par SMS, au mobile ci-dessus
          </label>
          <label class="css__toggle">
            <input v-model="emailEnabled" type="checkbox" />
            Chaque demande par email
          </label>
        </div>

        <template v-if="smsEnabled">
          <fieldset class="cs-field">
            <legend class="cs-label">SMS immédiat pour</legend>
            <div class="css__chips">
              <label
                v-for="option in CLIENT_SPACE_REQUEST_TYPE_OPTIONS"
                :key="option.value"
                class="css__chip"
                :class="{ 'css__chip--on': smsTypes.includes(option.value) }"
              >
                <input
                  type="checkbox"
                  class="css__check"
                  :checked="smsTypes.includes(option.value)"
                  @change="toggleSmsType(option.value)"
                />
                {{ option.label }}
              </label>
            </div>
            <span class="css__hint">Les autres demandes arrivent par email seulement.</span>
          </fieldset>

          <fieldset class="cs-field">
            <legend class="cs-label">Ne pas déranger</legend>
            <div class="css__hours">
              <span>de</span>
              <select v-model.number="quietStartHour" class="cs-input css__hour" aria-label="Début de la plage">
                <option v-for="hour in HOURS" :key="hour" :value="hour">{{ hour }} h</option>
              </select>
              <span>à</span>
              <select v-model.number="quietEndHour" class="cs-input css__hour" aria-label="Fin de la plage">
                <option v-for="hour in HOURS" :key="hour" :value="hour">{{ hour }} h</option>
              </select>
            </div>
            <span class="css__hint">Les SMS reçus dans la plage partent à sa fin.</span>
          </fieldset>
        </template>
      </fieldset>

      <ClientSpaceSaveBar
        :is-busy="isSaving"
        :can-save="canSave"
        :error-message="errorMessage"
        :show-saved="hasSaved && !hasChanges"
      />
    </form>
  </ClientSpaceSection>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType, Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import type { AssistantWidgetLang } from '~/types/AiAssistant'
import type {
  AiAssistantClientLanguageOption,
  AiAssistantClientRequestType,
  AiAssistantClientSettings,
  AiAssistantClientSettingsUpdate,
} from '~/types/AiAssistantClientSpace'
import type { ClientSpaceSettingsEmits, ClientSpaceSettingsProps } from '~/types/ClientSpaceSettings'
import { CLIENT_SPACE_REQUEST_TYPE_OPTIONS } from '~/constants/ClientSpaceRequestTypes'

/** Whole hours of the day, for the quiet window. */
const HOURS: number[] = Array.from({ length: 24 }, (_: unknown, hour: number): number => hour)

/**
 * The few settings a client changes alone: the assistant's first name, its languages and the alerts (mobile,
 * SMS and email switches, the request types texted at once, the quiet window).
 * @param settings The current settings, defaults applied.
 * @param languageOptions The languages the widget can speak.
 * @param isSaving A save is in flight.
 * @param errorMessage Why the last save was refused, if it was.
 * @param hasSaved The last save went through.
 */
const props: ClientSpaceSettingsProps = defineProps({
  settings: { type: Object as PropType<AiAssistantClientSettings>, required: true },
  languageOptions: { type: Array as PropType<AiAssistantClientLanguageOption[]>, required: true },
  isSaving: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  hasSaved: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceSettingsEmits> = defineEmits<ClientSpaceSettingsEmits>()

const assistantName: Ref<string> = ref(props.settings.assistant_name)
const languages: Ref<AssistantWidgetLang[]> = ref([...props.settings.languages])
const alertPhone: Ref<string> = ref(props.settings.alert_phone ?? '')
const smsEnabled: Ref<boolean> = ref(props.settings.alert_sms_enabled)
const emailEnabled: Ref<boolean> = ref(props.settings.alert_email_enabled)
const smsTypes: Ref<AiAssistantClientRequestType[]> = ref([...props.settings.alert_sms_types])
const quietStartHour: Ref<number> = ref(props.settings.alert_quiet_start_hour)
const quietEndHour: Ref<number> = ref(props.settings.alert_quiet_end_hour)

const changes: ComputedRef<AiAssistantClientSettingsUpdate> = computed((): AiAssistantClientSettingsUpdate => {
  const update: AiAssistantClientSettingsUpdate = {}
  const name: string = assistantName.value.trim()
  if (name && name !== props.settings.assistant_name) update.assistant_name = name
  if ([...languages.value].sort().join() !== [...props.settings.languages].sort().join()) {
    update.languages = [...languages.value]
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

// Languages set only by the operator (not offered here) stay on the server: an empty choice is refused only
// when the client emptied it.
const canSave: ComputedRef<boolean> = computed(
  (): boolean => hasChanges.value && (changes.value.languages === undefined || changes.value.languages.length > 0),
)

/**
 * Add or remove a language from the offer.
 * @param code The language toggled.
 */
function toggleLanguage(code: AssistantWidgetLang): void {
  languages.value = languages.value.includes(code)
    ? languages.value.filter((item: AssistantWidgetLang): boolean => item !== code)
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
.css__form {
  display: grid;
  gap: 18px;
}

.css__fields {
  display: grid;
  gap: 18px;
  margin: 0;
  padding: 0;
  border: 0;
  min-width: 0;
}

.css__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.css__chip {
  cursor: pointer;
  border: 1px solid var(--cs-line);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 13px;
  background: var(--cs-card);
}

.css__chip--on {
  border-color: var(--a-accent);
  background: color-mix(in srgb, var(--a-accent) 14%, #fff);
}

.css__check {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.css__toggles {
  display: grid;
  gap: 10px;
  font-size: 14px;
}

.css__toggle {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.css__toggle input {
  margin-top: 3px;
  accent-color: var(--a-accent);
}

.css__hint {
  font-size: 12.5px;
  color: var(--cs-ink-dim);
}

.css__hours {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}

.css__hour {
  width: auto;
}
</style>
