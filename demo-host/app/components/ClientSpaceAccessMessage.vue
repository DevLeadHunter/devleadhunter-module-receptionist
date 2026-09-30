<template>
  <main v-if="props.state === 'loading'" class="cs-message">
    <p class="cs-muted">Chargement…</p>
  </main>

  <main v-else-if="props.state === 'expired'" class="cs-message">
    <h1 class="cs-message__title">Ce lien a expiré</h1>
    <p class="cs-muted">
      Pour protéger vos demandes, un lien qui n’a pas été ouvert depuis {{ LINK_LIFETIME_DAYS }} jours expire.
    </p>
    <button v-if="props.renewState === 'idle'" type="button" class="cs-btn cs-btn--primary" @click="emit('renew')">
      Recevoir un nouveau lien par e-mail
    </button>
    <p v-else-if="props.renewState === 'sending'" class="cs-muted">Envoi…</p>
    <p v-else-if="props.renewState === 'sent'" class="cs-notice">
      C’est envoyé : ouvrez le nouveau lien depuis votre boîte mail.
    </p>
    <p v-else class="cs-notice cs-notice--error">
      Envoi impossible pour le moment : répondez à l’un de nos emails, on vous renvoie un lien.
    </p>
  </main>

  <main v-else class="cs-message">
    <h1 class="cs-message__title">{{ props.state === 'unavailable' ? 'Espace indisponible' : 'Lien invalide' }}</h1>
    <p class="cs-muted">
      {{
        props.state === 'unavailable'
          ? 'Réessayez dans quelques minutes.'
          : 'Ce lien n’ouvre aucun espace. Utilisez le dernier lien reçu par e-mail ou par SMS.'
      }}
    </p>
  </main>
</template>

<script lang="ts" setup>
import type { EmitFn, PropType } from 'vue'
import type { AiAssistantClientRenewState, AiAssistantClientSpaceState } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceAccessMessageEmits, ClientSpaceAccessMessageProps } from '~/types/ClientSpaceAccessMessage'

const props: ClientSpaceAccessMessageProps = defineProps({
  state: { type: String as PropType<AiAssistantClientSpaceState>, required: true },
  renewState: { type: String as PropType<AiAssistantClientRenewState>, required: true },
})

const emit: EmitFn<ClientSpaceAccessMessageEmits> = defineEmits<ClientSpaceAccessMessageEmits>()

/** Days a link stays valid after its last opening, as the API signs it. */
const LINK_LIFETIME_DAYS: number = 30
</script>
