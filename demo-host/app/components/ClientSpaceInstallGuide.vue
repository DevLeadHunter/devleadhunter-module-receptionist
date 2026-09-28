<template>
  <div class="cs-screen__body">
    <p v-if="props.installed" class="cs-notice cs-notice--ok">
      Installée sur {{ props.installed.host }}, vue le {{ props.installed.seen_label }}.
    </p>
    <p class="cs-sec">La ligne à coller</p>
    <div class="cs-block">
      <p class="cs-text">
        Collez cette ligne sur votre site, juste avant la fin de chaque page (la balise
        <code>{{ BODY_END_TAG }}</code
        >) : {{ props.assistantName }} apparaît en bas à droite.
      </p>
      <pre class="cs-code">{{ props.embedSnippet }}</pre>
      <div class="cs-screen__actions">
        <button type="button" class="cs-btn" @click="copyText(props.embedSnippet ?? '', 'snippet')">
          <ClientSpaceIcon :name="copiedKey === 'snippet' ? 'check' : 'code'" />
          {{ copiedKey === 'snippet' ? 'Copiée' : 'Copier la ligne' }}
        </button>
      </div>
    </div>
    <p class="cs-sec">Ou à envoyer</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        Quelqu’un s’occupe de votre site (une agence, un proche, votre prestataire) ? Envoyez-lui la ligne. Vous pouvez
        aussi répondre à l’un de nos emails : on l’installe avec vous.
      </p>
      <div class="cs-screen__actions">
        <a class="cs-btn" :href="snippetMailto"><ClientSpaceIcon name="mail" />Envoyer par email</a>
      </div>
    </div>
    <p class="cs-sec">Vérifier</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        Ouvrez votre site : la bulle de {{ props.assistantName }} doit apparaître en bas à droite de chaque page.
        Testez-la comme un client et laissez votre numéro : la demande arrive ici, et par SMS.
      </p>
      <div v-if="props.websiteUrl" class="cs-screen__actions">
        <a class="cs-btn" :href="props.websiteUrl" target="_blank" rel="noopener">
          <ClientSpaceIcon name="external-link" />Ouvrir votre site
        </a>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientInstalled } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceInstallGuideProps } from '~/types/ClientSpaceInstallGuide'
import type { UseClientSpaceClipboardReturn } from '~/types/UseClientSpaceClipboard'
import { useClientSpaceClipboard } from '~/composables/useClientSpaceClipboard'

const props: ClientSpaceInstallGuideProps = defineProps({
  installed: { type: Object as PropType<AiAssistantClientInstalled | null>, default: null },
  embedSnippet: { type: String as PropType<string | null>, default: null },
  websiteUrl: { type: String as PropType<string | null>, default: null },
  assistantName: { type: String, required: true },
  businessName: { type: String, required: true },
})

const { copiedKey, copyText }: UseClientSpaceClipboardReturn = useClientSpaceClipboard()

/** The tag the line to paste goes before, shown as text (a template cannot carry it as markup). */
const BODY_END_TAG: string = '</body>'

/** An email carrying the line to paste, for whoever looks after the website. */
const snippetMailto: ComputedRef<string> = computed((): string => {
  const subject: string = `${props.assistantName}, la réceptionniste du site ${props.businessName}`
  const body: string =
    `Bonjour,\n\nPouvez-vous coller cette ligne sur le site ${props.businessName}, juste avant la balise ` +
    `${BODY_END_TAG} de chaque page ?\n\n${props.embedSnippet ?? ''}\n\nMerci !`
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
})
</script>
