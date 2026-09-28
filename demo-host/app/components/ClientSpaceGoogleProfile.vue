<template>
  <div class="cs-screen__body">
    <p class="cs-sec">L’adresse de {{ props.assistantName }}</p>
    <div class="cs-block">
      <p class="cs-text">
        Sur votre fiche Google, deux boutons peuvent mener à {{ props.assistantName }} : « Site web » et « Prendre
        rendez-vous ». Collez-y cette adresse : vos clients y arrivent en un geste, même sans site.
      </p>
      <pre class="cs-code">{{ props.googleProfile.page_url }}</pre>
      <div class="cs-screen__actions">
        <button type="button" class="cs-btn" @click="copyText(props.googleProfile.page_url, 'link')">
          <ClientSpaceIcon :name="copiedKey === 'link' ? 'check' : 'code'" />
          {{ copiedKey === 'link' ? 'Copiée' : 'Copier l’adresse' }}
        </button>
      </div>
    </div>
    <p class="cs-sec">Où la coller</p>
    <div class="cs-block">
      <ol class="cs-steps">
        <li>
          Cherchez votre entreprise sur Google, connecté au compte qui gère la fiche, puis « Modifier le profil ».
        </li>
        <li>Dans « Coordonnées », champ « Site web » : collez l’adresse.</li>
        <li>
          Dans « Réservations » (ou « Lien de rendez-vous »), collez la même adresse, puis enregistrez. Google l’affiche
          en quelques minutes.
        </li>
      </ol>
      <label class="cs-check">
        <input
          type="checkbox"
          :checked="props.googleProfile.is_linked"
          :disabled="props.isSaving || props.readOnly"
          @change="emitLinked"
        />
        <span>
          <b>C’est fait, l’adresse est sur ma fiche</b>
          <span>{{ linkedStepHint }}</span>
        </span>
      </label>
      <p v-if="props.errorMessage" class="cs-notice cs-notice--error">{{ props.errorMessage }}</p>
    </div>
    <p class="cs-sec">Votre messagerie vocale</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        Un appel manqué peut encore aboutir : enregistrez ce message, il renvoie vers {{ props.assistantName }}.
      </p>
      <pre class="cs-code cs-code--prose">{{ props.googleProfile.voicemail_text }}</pre>
      <div class="cs-screen__actions">
        <button type="button" class="cs-btn" @click="copyText(props.googleProfile.voicemail_text, 'voicemail')">
          <ClientSpaceIcon :name="copiedKey === 'voicemail' ? 'check' : 'message-square'" />
          {{ copiedKey === 'voicemail' ? 'Copié' : 'Copier le message' }}
        </button>
      </div>
    </div>
    <p class="cs-sec">QR à imprimer</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">Carte de visite, camionnette, devis : la même adresse, à scanner.</p>
      <div class="cs-qr" v-html="props.googleProfile.qr_svg"></div>
      <div class="cs-screen__actions">
        <a class="cs-btn" :href="qrDownloadHref" :download="`qr-${props.assistantName}.svg`">
          <ClientSpaceIcon name="image" />Télécharger le QR
        </a>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientGoogleProfile } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceGoogleProfileEmits, ClientSpaceGoogleProfileProps } from '~/types/ClientSpaceGoogleProfile'
import type { UseClientSpaceClipboardReturn } from '~/types/UseClientSpaceClipboard'
import { useClientSpaceClipboard } from '~/composables/useClientSpaceClipboard'

const props: ClientSpaceGoogleProfileProps = defineProps({
  googleProfile: { type: Object as PropType<AiAssistantClientGoogleProfile>, required: true },
  assistantName: { type: String, required: true },
  isSaving: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  readOnly: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceGoogleProfileEmits> = defineEmits<ClientSpaceGoogleProfileEmits>()

const { copiedKey, copyText }: UseClientSpaceClipboardReturn = useClientSpaceClipboard()

const linkedStepHint: ComputedRef<string> = computed((): string =>
  props.googleProfile.is_linked && props.googleProfile.linked_at_label
    ? `Posée le ${props.googleProfile.linked_at_label}.`
    : 'Cochez quand c’est fait : l’étape passe en vert sur votre accueil.',
)

/** The QR code as a file the client saves: the API's SVG in a data URL. */
const qrDownloadHref: ComputedRef<string> = computed((): string => {
  const svg: string = props.googleProfile.qr_svg
  return svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` : ''
})

/**
 * Hand over whether the client ticked « C’est fait », as the checkbox now reads.
 * @param event - The checkbox's change event.
 */
function emitLinked(event: Event): void {
  if (event.target instanceof HTMLInputElement) emit('linked', event.target.checked)
}
</script>
