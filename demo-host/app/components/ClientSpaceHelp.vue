<template>
  <div class="cs-screen__body">
    <p class="cs-sec">Une question ?</p>
    <div class="cs-block">
      <p class="cs-text">
        Répondez à l’un des emails que vous avez reçus de nous, ou écrivez-nous depuis l’adresse de votre entreprise :
        on vous répond en personne, généralement dans la journée.
      </p>
    </div>
    <p class="cs-sec">Votre lien</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        <template v-if="props.isExample">Cet exemple n’a pas de lien personnel.</template>
        <template v-else>
          Ce lien personnel se prolonge à chaque ouverture : tant que vous l’ouvrez au moins une fois par mois, il reste
          valable (pour l’instant jusqu’au {{ props.linkExpiresLabel }}). Il donne accès à vos demandes : ne le
          transférez pas. S’il expire, vous en recevez un nouveau par email.
        </template>
      </p>
    </div>
    <p class="cs-sec">Sur votre téléphone</p>
    <div class="cs-block">
      <p class="cs-text cs-text--dim">
        Ajoutez cette page à l’écran d’accueil de votre téléphone (bouton Partager, puis « Sur l’écran d’accueil ») :
        vous retrouvez vos demandes d’un geste, comme une application.
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ClientSpaceHelpProps } from '~/types/ClientSpaceHelp'

const props: ClientSpaceHelpProps = defineProps({
  isExample: { type: Boolean, default: false },
  linkExpiresLabel: { type: String, required: true },
})
</script>
