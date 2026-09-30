<template>
  <div class="cs-mailbox">
    <div v-if="props.mailbox.status !== 'connected'" class="cs-block cs-mailbox__connect">
      <span class="cs-todo__icon" :class="{ 'cs-todo__icon--amber': isAccessLost }"
        ><ClientSpaceIcon name="mail"
      /></span>
      <p class="cs-mailbox__title">
        {{ isAccessLost ? 'L’accès à votre boîte mail a été perdu' : 'Vos réponses aux e-mails, prêtes à envoyer' }}
      </p>
      <p class="cs-text cs-text--dim">
        {{
          isAccessLost
            ? 'Plus aucune réponse n’est préparée. Reconnectez votre Gmail pour que la préparation reprenne.'
            : `Quand un client vous écrit, ${props.assistantName} prépare la réponse dans vos brouillons Gmail. Vous la relisez et vous l’envoyez : rien ne part sans vous.`
        }}
      </p>
      <button
        v-if="!props.readOnly"
        type="button"
        class="cs-btn cs-btn--primary"
        :disabled="props.isBusy"
        @click="emit('connect')"
      >
        {{ isAccessLost ? 'Reconnecter mon Gmail' : 'Connecter mon Gmail' }}
      </button>
      <p v-if="!props.readOnly" class="cs-text cs-text--dim cs-mailbox__hint">
        Google s’ouvre dans un nouvel onglet : autorisez la lecture de vos e-mails et la préparation des brouillons,
        puis revenez ici. Seules les boîtes Gmail peuvent être connectées.
      </p>
      <p v-if="props.mailbox.last_error" class="cs-notice cs-notice--error">
        Dernier problème le {{ props.mailbox.last_error }}
      </p>
      <p v-if="props.errorMessage" class="cs-notice cs-notice--error">{{ props.errorMessage }}</p>
    </div>

    <template v-else>
      <p class="cs-sec">Votre boîte Gmail</p>
      <div class="cs-block cs-mailbox__connected">
        <p class="cs-text">
          Connectée : <b class="cs-mailbox__address">{{ props.mailbox.account_email }}</b>
        </p>
        <p class="cs-text cs-text--dim">
          {{ props.assistantName }} lit les nouveaux e-mails de vos clients et prépare chaque réponse dans vos
          brouillons Gmail. Vous la relisez, vous la corrigez si besoin, puis vous l’envoyez.
        </p>
        <p class="cs-text cs-mailbox__count">{{ draftsLabel }}</p>
        <p v-if="props.mailbox.has_reached_daily_cap" class="cs-notice cs-mailbox__inset">
          Beaucoup d’e-mails aujourd’hui : les suivants n’auront pas de brouillon avant demain.
        </p>
        <div class="cs-mailbox__actions">
          <a class="cs-btn cs-btn--primary" :href="props.mailbox.drafts_url" target="_blank" rel="noopener noreferrer">
            <ClientSpaceIcon name="external-link" />Ouvrir mes brouillons Gmail
          </a>
          <button
            v-if="!props.readOnly"
            type="button"
            class="cs-btn"
            :disabled="props.isBusy"
            @click="emit('disconnect')"
          >
            Déconnecter
          </button>
        </div>
        <p v-if="!props.readOnly" class="cs-hint cs-mailbox__inset">
          Déconnecter arrête la préparation des réponses et efface l’accès gardé ici.
        </p>
        <p v-if="props.errorMessage" class="cs-notice cs-notice--error cs-mailbox__inset">{{ props.errorMessage }}</p>
      </div>
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, EmitFn, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientMailbox } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceMailboxEmits, ClientSpaceMailboxProps } from '~/types/ClientSpaceMailbox'

const props: ClientSpaceMailboxProps = defineProps({
  mailbox: { type: Object as PropType<AiAssistantClientMailbox>, required: true },
  assistantName: { type: String, required: true },
  isBusy: { type: Boolean, default: false },
  errorMessage: { type: String as PropType<string | null>, default: null },
  readOnly: { type: Boolean, default: false },
})

const emit: EmitFn<ClientSpaceMailboxEmits> = defineEmits<ClientSpaceMailboxEmits>()

const isAccessLost: ComputedRef<boolean> = computed((): boolean => props.mailbox.status === 'error')

const draftsLabel: ComputedRef<string> = computed((): string => {
  const count: number = props.mailbox.drafts_this_month
  if (count === 0) return 'Aucun brouillon préparé ce mois-ci pour l’instant.'
  return count === 1 ? '1 brouillon préparé ce mois-ci.' : `${count} brouillons préparés ce mois-ci.`
})
</script>

<style scoped>
.cs-mailbox {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.cs-mailbox__connect {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  justify-items: start;
  margin-top: 16px;
  padding: 18px 16px;
}

.cs-mailbox__connect .cs-text {
  padding: 0;
}

.cs-mailbox__connect .cs-btn {
  width: 100%;
  margin-top: 4px;
}

.cs-mailbox__title {
  margin: 0;
  font-size: 16.5px;
  font-weight: 600;
}

.cs-mailbox__hint {
  font-size: 13px;
}

.cs-mailbox__connected {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  padding: 14px 0 16px;
}

.cs-mailbox__connected .cs-text {
  padding: 0 16px;
}

.cs-mailbox__count {
  font-weight: 600;
}

.cs-mailbox__address {
  overflow-wrap: anywhere;
}

.cs-mailbox__actions {
  display: grid;
  gap: 10px;
  padding: 0 16px;
}

.cs-mailbox__inset {
  padding: 0 16px;
}
</style>
