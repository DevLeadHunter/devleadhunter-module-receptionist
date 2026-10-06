<template>
  <div class="flex min-h-0 flex-1 flex-col" :data-no-pull-to-refresh="hasPendingChanges ? '' : undefined">
    <UiLoader v-if="pending" label="Chargement de la réceptionniste…" />

    <div
      v-else-if="loadError"
      class="card m-4 border-[var(--app-red)]/30 bg-[var(--app-red-soft)] p-6 text-[var(--app-red)]"
    >
      {{ loadError }}
    </div>

    <template v-else-if="assistant">
      <header
        class="flex shrink-0 items-center gap-2 border-b border-[var(--app-line)] bg-[var(--app-surface)] px-3 py-2 md:px-4"
      >
        <NuxtLink
          to="/dashboard/ai-assistants"
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
          title="Retour aux réceptionnistes"
          aria-label="Retour aux réceptionnistes"
        >
          <UIcon name="i-lucide-arrow-left" class="h-5 w-5" />
        </NuxtLink>
        <AssistantPortrait
          :url="portraitUrl"
          :name="assistant.assistant_name"
          :accent-color="assistant.accent_color"
          :background="shownOwnImageBackground(assistant)"
          size-class="h-9 w-9 text-sm"
        />
        <div class="min-w-0 flex-1">
          <div class="flex min-w-0 items-center gap-2">
            <h1 class="truncate text-base font-semibold text-[var(--app-ink)]">{{ assistant.business_name }}</h1>
            <span
              :class="[
                'inline-flex shrink-0 items-center gap-1.5 rounded-full p-1.5 text-[11px] font-medium sm:px-2 sm:py-0.5',
                statusPillClass,
              ]"
            >
              <span class="h-1.5 w-1.5 rounded-full bg-current" :title="lifetimeLabel"></span>
              <span class="hidden sm:inline">{{ lifetimeLabel }}</span>
              <span class="sr-only sm:hidden">{{ lifetimeLabel }}</span>
            </span>
          </div>
          <p class="truncate text-xs text-[var(--app-ink-soft)]">{{ assistantFactsLine }}</p>
        </div>
        <template v-if="hasPendingChanges">
          <button
            type="button"
            class="btn-secondary inline-flex h-10 items-center gap-2 px-3 sm:px-4"
            title="Annuler les modifications"
            aria-label="Annuler les modifications"
            :disabled="isPublishing"
            @click="resetPendingChanges"
          >
            <UIcon name="i-lucide-undo-2" class="h-4 w-4 sm:hidden" />
            <span class="hidden sm:inline">Annuler</span>
          </button>
          <button
            type="button"
            class="btn-primary inline-flex h-10 items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isPublishing"
            @click="publishPendingChanges"
          >
            <UIcon name="i-lucide-upload" class="h-4 w-4" />
            {{ isPublishing ? 'Publication…' : 'Publier' }}
          </button>
        </template>
        <template v-else>
          <button
            type="button"
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[var(--app-line)] text-[var(--app-ink)] transition-colors hover:bg-[var(--app-surface-2)]"
            :title="copied ? 'Lien copié' : 'Copier le lien de la démo'"
            :aria-label="copied ? 'Lien copié' : 'Copier le lien de la démo'"
            @click="copy(assistant.demo_url)"
          >
            <UIcon :name="copied ? 'i-lucide-check' : 'i-lucide-link'" class="h-4 w-4" />
          </button>
          <button
            type="button"
            class="btn-primary inline-flex h-10 items-center gap-2"
            title="Ouvrir la démo"
            aria-label="Ouvrir la démo"
            @click="openExternalUrl(demoUrl)"
          >
            <UIcon name="i-lucide-external-link" class="h-4 w-4" />
            <span class="hidden sm:inline">Ouvrir</span>
          </button>
        </template>
      </header>

      <p
        v-if="assistant.needs_follow_up"
        class="shrink-0 border-b border-[var(--app-accent)]/40 bg-[var(--app-accent-soft)] px-4 py-2 text-xs text-[var(--app-accent-ink)]"
      >
        Les deux relances automatiques sont parties. Il manque encore :
        {{ missingStartStepsLabel(assistant.missing_start_steps) }}.
      </p>
      <p
        v-else-if="assistant.churn_risk"
        class="shrink-0 border-b border-[var(--app-accent)]/40 bg-[var(--app-accent-soft)] px-4 py-2 text-xs text-[var(--app-accent-ink)]"
      >
        Abonné depuis plus de 30 jours, aucune conversation ni demande sur les 30 derniers jours : vérifiez que la bulle
        apparaît sur son site.
      </p>

      <div v-show="isPreviewShown" class="flex min-h-0 flex-1 flex-col">
        <div class="flex shrink-0 justify-center border-b border-[var(--app-line)] bg-[var(--app-surface)] py-2">
          <div
            class="flex overflow-hidden rounded-full border border-[var(--app-line)] bg-[var(--app-bg)]"
            role="group"
            aria-label="Format de l'aperçu"
          >
            <button
              v-for="device in previewDevices"
              :key="device.key"
              type="button"
              :class="[
                'flex h-9 items-center gap-1.5 px-4 text-xs font-medium transition-colors',
                previewDevice === device.key
                  ? 'bg-[var(--app-ink)] text-[var(--app-bg)]'
                  : 'text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]',
              ]"
              :aria-pressed="previewDevice === device.key"
              @click="previewDevice = device.key"
            >
              <UIcon :name="device.icon" class="h-3.5 w-3.5" />
              {{ device.label }}
            </button>
          </div>
        </div>

        <div ref="workAreaElement" class="flex min-h-0 flex-1 flex-col">
          <div class="min-h-0 flex-1">
            <AtelierDevicePreview
              :page-url="demoUrl"
              :device="previewDevice"
              :preview-message="previewMessage"
              :reload-nonce="previewReloadNonce"
            />
          </div>

          <Transition name="atelier-sheet">
            <section
              v-show="isToolSheetOpen"
              ref="sheetElement"
              class="relative flex shrink-0 flex-col rounded-t-2xl border-t border-[var(--app-line)] bg-[var(--app-surface)] shadow-[0_-12px_40px_rgba(0,0,0,0.08)] outline-none"
              :style="sheetStyle"
              :aria-label="activeToolMeta?.title"
              tabindex="-1"
              data-no-pull-to-refresh
            >
              <button
                type="button"
                class="flex h-5 w-full shrink-0 cursor-grab touch-none items-end justify-center active:cursor-grabbing"
                :title="sheetSize === 'expanded' ? 'Réduire le volet' : 'Agrandir le volet'"
                :aria-label="sheetSize === 'expanded' ? 'Réduire le volet' : 'Agrandir le volet'"
                :aria-expanded="sheetSize === 'expanded'"
                @pointerdown="startSheetDrag"
                @pointermove="followSheetDrag"
                @pointerup="endSheetDrag"
                @pointercancel="cancelSheetDrag"
                @click="toggleSheetSize"
              >
                <span class="h-1 w-10 rounded-full bg-[var(--app-line)]"></span>
              </button>
              <div class="flex shrink-0 items-start gap-3 px-4 pt-1 pb-2 md:px-5">
                <div class="min-w-0 flex-1">
                  <h2 class="text-sm font-semibold text-[var(--app-ink)]">{{ activeToolMeta?.title }}</h2>
                  <p class="truncate text-xs text-[var(--app-ink-soft)]">{{ activeToolHint }}</p>
                </div>
                <button
                  type="button"
                  class="-mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[var(--app-ink-soft)] transition-colors hover:bg-[var(--app-surface-2)] hover:text-[var(--app-ink)]"
                  title="Fermer le volet"
                  aria-label="Fermer le volet"
                  @click="closeActiveTool"
                >
                  <UIcon name="i-lucide-x" class="h-4 w-4" />
                </button>
              </div>

              <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-4 md:px-5">
                <AssistantSettingsForm
                  ref="identityForm"
                  :assistant="assistant"
                  section="identity"
                  @saved="onAssistantSaved"
                  @draft="onDraftChange"
                />
              </div>
            </section>
          </Transition>
        </div>
      </div>

      <section
        v-show="isPageToolOpen"
        class="min-h-0 flex-1 overflow-y-auto p-4 md:p-6"
        :aria-label="activeToolMeta?.title"
      >
        <div class="mx-auto w-full max-w-4xl space-y-4">
          <div v-if="activeToolMeta && activeTool !== 'plus'" class="px-1">
            <h2 class="text-base font-semibold text-[var(--app-ink)]">{{ activeToolMeta.title }}</h2>
            <p class="text-xs text-[var(--app-ink-soft)]">{{ activeToolHint }}</p>
          </div>

          <div v-show="activeTool === 'reponses'" class="space-y-4">
            <AssistantFaqCard :assistant-id="assistant.id" :assistant-name="assistant.assistant_name" />
            <div class="card flex flex-wrap items-center justify-between gap-3 p-5">
              <div class="min-w-0">
                <h3 class="text-sm font-semibold text-[var(--app-ink)]">Ce qu'elle lit</h3>
                <p class="mt-0.5 text-xs text-[var(--app-ink-soft)]">
                  Le site du commerce, sa fiche Google et vos documents.
                </p>
              </div>
              <button type="button" class="btn-secondary h-10 text-xs" @click="openSources">
                <UIcon name="i-lucide-library" class="h-3.5 w-3.5" />
                Ouvrir les sources
              </button>
            </div>
          </div>

          <div v-show="activeTool === 'demandes'" class="space-y-4">
            <AssistantRecentRequests
              :assistant-id="assistant.id"
              :assistant-name="assistant.assistant_name"
              :requests="requests"
              @open="openRequest"
            />
            <div class="card flex flex-wrap items-center justify-between gap-3 p-5">
              <div class="min-w-0">
                <h3 class="text-sm font-semibold text-[var(--app-ink)]">Conversations</h3>
                <p class="mt-0.5 text-xs text-[var(--app-ink-soft)]">{{ conversationsLabel }}</p>
              </div>
              <button type="button" class="btn-secondary h-10 text-xs" @click="openConversations">
                <UIcon name="i-lucide-messages-square" class="h-3.5 w-3.5" />
                Lire les conversations
              </button>
            </div>
          </div>

          <div v-show="activeTool === 'alertes'" class="card p-5">
            <AssistantSettingsForm ref="alertsForm" :assistant="assistant" section="alerts" @saved="onAssistantSaved" />
          </div>

          <div v-show="activeTool === 'video'" class="card p-5">
            <AssistantVideoCard
              :assistant="assistant"
              :is-busy="isVideoBusy"
              :is-removing-video="isRemovingVideo"
              :is-taking-longer-than-expected="isVideoTakingLongerThanExpected"
              :is-refreshing-video="isRefreshingVideo"
              :is-framed="false"
              is-heading-hidden
              @generate="generateVideo"
              @remove-video="videoDeleteConfirmModal?.open()"
              @refresh-video="refreshVideoStatusNow"
            />
          </div>

          <div v-show="activeTool === 'plus'" class="space-y-4">
            <div class="grid grid-cols-2 gap-3 @5xl:grid-cols-4">
              <UiStatCard
                v-for="stat in stats"
                :key="stat.label"
                :label="stat.label"
                :value="stat.value"
                :icon="stat.icon"
                accent="neutral"
              />
            </div>

            <div class="card p-5">
              <h2 class="text-sm font-semibold text-[var(--app-ink)]">
                {{ isSold ? 'Adresse de sa page' : 'Lien de la démo' }}
              </h2>
              <p class="mt-1 text-xs text-[var(--app-ink-soft)]">{{ demoLinkHint }}</p>
              <div class="mt-3 flex items-center gap-2">
                <input
                  :value="assistant.demo_url"
                  readonly
                  class="input-field h-10 flex-1 truncate text-xs"
                  aria-label="Lien de la démo"
                />
                <button
                  type="button"
                  class="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-[var(--app-line)] text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]"
                  :title="copied ? 'Lien copié !' : 'Copier le lien'"
                  :aria-label="copied ? 'Lien copié' : 'Copier le lien'"
                  @click="copy(assistant.demo_url)"
                >
                  <UIcon :name="copied ? 'i-lucide-check' : 'i-lucide-copy'" class="h-4 w-4" />
                </button>
              </div>
            </div>

            <div class="card p-5">
              <h2 class="text-sm font-semibold text-[var(--app-ink)]">Script pour le site du client</h2>
              <p class="mt-1 text-xs text-[var(--app-ink-soft)]">
                Une ligne à coller avant la balise de fin du site : la bulle apparaît en bas à droite.
              </p>
              <div class="mt-3 flex items-center gap-2">
                <input
                  :value="assistant.embed_snippet"
                  readonly
                  class="input-field font-label h-10 flex-1 truncate text-xs"
                  aria-label="Script à coller sur le site du client"
                />
                <button
                  type="button"
                  class="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-[var(--app-line)] text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]"
                  :title="isSnippetCopied ? 'Script copié !' : 'Copier le script'"
                  :aria-label="isSnippetCopied ? 'Script copié' : 'Copier le script'"
                  @click="copySnippet"
                >
                  <UIcon :name="isSnippetCopied ? 'i-lucide-check' : 'i-lucide-copy'" class="h-4 w-4" />
                </button>
              </div>
            </div>

            <AssistantInstallGuideCard :embed-snippet="assistant.embed_snippet" />

            <div class="card p-5">
              <div class="flex items-center justify-between gap-3">
                <h2 class="text-sm font-semibold text-[var(--app-ink)]">Espace du client</h2>
                <span v-if="isSold" class="app-badge app-badge--strong">Vendu</span>
              </div>
              <p class="mt-1 text-xs text-[var(--app-ink-soft)]">
                Ses demandes, son rapport, ses réglages et son abonnement, sur un lien envoyé
                {{ businessRecipientLabel }}.
              </p>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  :class="[isSold ? 'btn-primary' : 'btn-secondary', 'h-10 text-xs disabled:opacity-50']"
                  :disabled="isSendingClientLink"
                  @click="clientSpaceConfirmModal?.open()"
                >
                  <UIcon name="i-lucide-user-round-plus" class="h-3.5 w-3.5" />
                  {{ isSendingClientLink ? 'Envoi…' : "Envoyer l'espace client" }}
                </button>
                <button
                  type="button"
                  class="btn-secondary h-10 text-xs disabled:opacity-50"
                  :disabled="isRevokingClientLinks"
                  @click="revokeLinksConfirmModal?.open()"
                >
                  <UIcon name="i-lucide-link-2-off" class="h-3.5 w-3.5" />
                  {{ isRevokingClientLinks ? 'Coupure…' : 'Couper les anciens liens' }}
                </button>
              </div>
              <div v-if="clientSpaceLinkForManualCopy" class="mt-3 flex items-center gap-2">
                <input
                  :value="clientSpaceLinkForManualCopy"
                  readonly
                  class="input-field h-10 flex-1 truncate text-xs"
                  aria-label="Lien de l'espace client à copier"
                />
                <button
                  type="button"
                  class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--app-line)] text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]"
                  title="Copier le lien de l'espace client"
                  aria-label="Copier le lien de l'espace client"
                  @click="copy(clientSpaceLinkForManualCopy)"
                >
                  <UIcon :name="copied ? 'i-lucide-check' : 'i-lucide-copy'" class="h-4 w-4" />
                </button>
              </div>
            </div>

            <div class="card p-5">
              <AssistantSubscriptionCard :assistant="assistant" :is-framed="false" />
            </div>

            <div class="card p-5">
              <h2 class="text-sm font-semibold text-[var(--app-ink)]">Informations</h2>
              <dl class="mt-3 grid gap-x-8 gap-y-2.5 text-sm @2xl:grid-cols-2">
                <div
                  v-for="row in informationRows"
                  :key="row.label"
                  class="flex justify-between gap-3 border-b border-[var(--app-line-soft)] pb-2"
                >
                  <dt class="shrink-0 text-[var(--app-ink-soft)]">{{ row.label }}</dt>
                  <dd class="truncate text-right text-[var(--app-ink)]">{{ row.value }}</dd>
                </div>
              </dl>
            </div>

            <div class="card p-5">
              <h2 class="text-sm font-semibold text-[var(--app-ink)]">Après la vente</h2>
              <p class="mt-1 text-xs text-[var(--app-ink-soft)]">
                Reprendre les dernières données du prospect, ou enregistrer une vente faite hors Stripe.
              </p>
              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  class="btn-secondary h-10 text-xs disabled:opacity-50"
                  :disabled="isRegenerating"
                  @click="regenerateAssistant"
                >
                  <UIcon name="i-lucide-refresh-cw" class="h-3.5 w-3.5" />
                  {{ isRegenerating ? 'Régénération…' : 'Régénérer depuis le prospect' }}
                </button>
                <button
                  v-if="!isSold"
                  type="button"
                  class="btn-secondary h-10 text-xs disabled:opacity-50"
                  :disabled="isMarkingSold"
                  @click="soldConfirmModal?.open()"
                >
                  <UIcon name="i-lucide-badge-check" class="h-3.5 w-3.5" />
                  {{ isMarkingSold ? 'Enregistrement…' : 'Marquer comme vendu (hors Stripe)' }}
                </button>
              </div>
            </div>

            <div class="card border-[var(--app-red)]/30 p-5">
              <h2 class="text-sm font-semibold text-[var(--app-red)]">Supprimer la réceptionniste</h2>
              <p class="mt-1 text-xs text-[var(--app-ink-soft)]">
                Sa démo et son widget s'arrêtent ; ses documents, ses conversations, les demandes et la vidéo sont
                effacés. Les ventes et les abonnements passés restent.
              </p>
              <button
                type="button"
                class="btn-secondary mt-3 h-10 text-xs text-[var(--app-red)]"
                :disabled="isDeleting"
                @click="deleteConfirmModal?.open()"
              >
                <UIcon name="i-lucide-trash-2" class="h-3.5 w-3.5" />
                {{ isDeleting ? 'Suppression…' : 'Supprimer la réceptionniste' }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <nav
        class="flex shrink-0 items-stretch border-t border-[var(--app-line)] bg-[var(--app-surface)] pb-[env(safe-area-inset-bottom)]"
        aria-label="Outils de la réceptionniste"
      >
        <button
          v-for="tool in atelierTools"
          :key="tool.key"
          :ref="(element: Element | ComponentPublicInstance | null): void => registerToolButton(tool.key, element)"
          type="button"
          :class="[
            'relative flex min-h-16 min-w-0 flex-1 flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors [-webkit-tap-highlight-color:transparent] sm:text-[11px]',
            activeTool === tool.key
              ? 'text-[var(--app-ink)]'
              : 'text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]',
          ]"
          :aria-pressed="activeTool === tool.key"
          @click="toggleTool(tool.key)"
        >
          <span
            :class="[
              'flex h-8 w-12 items-center justify-center rounded-full transition-colors',
              activeTool === tool.key ? 'bg-[var(--app-ink)] text-[var(--app-bg)]' : '',
            ]"
          >
            <UIcon :name="tool.icon" class="h-5 w-5" />
          </span>
          <span class="max-w-full truncate px-0.5">{{ tool.label }}</span>
          <span
            v-if="toolWaitingCounts[tool.key]"
            class="absolute top-1.5 right-[calc(50%-28px)] min-w-4 rounded-full bg-[var(--app-ink)] px-1 text-center text-[10px] leading-4 font-semibold text-[var(--app-bg)] ring-2 ring-[var(--app-surface)]"
          >
            {{ toolWaitingCounts[tool.key] }}
          </span>
          <span v-if="toolWaitingCounts[tool.key]" class="sr-only">({{ toolWaitingCounts[tool.key] }} à traiter)</span>
          <span
            v-if="toolPendingChanges[tool.key]"
            class="absolute top-2 right-[calc(50%-18px)] h-2 w-2 rounded-full bg-[var(--app-accent)]"
            title="Modifications non publiées"
          ></span>
          <span v-if="toolPendingChanges[tool.key]" class="sr-only">(modifications non publiées)</span>
        </button>
      </nav>

      <UiConfirmModal
        ref="deleteConfirmModal"
        title="Supprimer la réceptionniste"
        :message="deleteConfirmMessage"
        confirm-text="Supprimer"
        cancel-text="Annuler"
        @confirm="removeAssistant"
      />
      <UiConfirmModal
        ref="clientSpaceConfirmModal"
        title="Envoyer l'espace client"
        :message="clientSpaceConfirmMessage"
        confirm-text="Envoyer"
        cancel-text="Annuler"
        confirm-button-variant="primary"
        @confirm="sendClientSpace"
      />
      <UiConfirmModal
        ref="revokeLinksConfirmModal"
        title="Couper les anciens liens"
        message="Tous les liens envoyés jusqu'ici, alertes SMS comprises, ne marcheront plus."
        confirm-text="Couper les liens"
        cancel-text="Annuler"
        @confirm="revokeClientLinks"
      />
      <UiConfirmModal
        ref="newClientLinkConfirmModal"
        title="Anciens liens coupés"
        :message="newClientLinkConfirmMessage"
        confirm-text="Envoyer un nouveau lien à l'entreprise"
        cancel-text="Plus tard"
        confirm-button-variant="primary"
        @confirm="sendClientSpace"
      />
      <UiConfirmModal
        ref="videoDeleteConfirmModal"
        title="Supprimer la vidéo"
        message="Supprimer la vidéo de prospection de cette réceptionniste ? Le lien envoyé dans les emails et SMS ne fonctionnera plus."
        confirm-text="Supprimer"
        cancel-text="Annuler"
        @confirm="removeVideo"
      />
      <UiConfirmModal
        ref="soldConfirmModal"
        title="Marquer comme vendu"
        :message="soldConfirmMessage"
        confirm-text="Marquer vendu"
        cancel-text="Annuler"
        confirm-button-variant="primary"
        @confirm="markSold"
      />
    </template>

    <UiVideoGenerationModal
      :open="videoProgress.isOpen.value"
      title="Génération de la vidéo"
      :steps="videoProgress.steps.value"
      :log-lines="videoProgress.logLines.value"
      :elapsed-seconds="videoProgress.elapsedSeconds.value"
      :error-message="videoProgress.errorMessage.value"
      :is-running="videoProgress.isRunning.value"
      @close="videoProgress.close()"
    />
  </div>
</template>

<script lang="ts" setup>
import type { ComponentPublicInstance, ComputedRef, Ref } from 'vue'
import type { UseVideoGenerationProgressReturn } from '~/composables/useVideoGenerationProgress'
import type {
  AiAssistantClientLink,
  AiAssistantEditForm,
  AiAssistantRequestItem,
  AiAssistantRequestsResponse,
  AiAssistantSummary,
} from '~/types/AiAssistant'
import type {
  AiAssistantAtelierToolKey,
  AiAssistantDetailStat,
  AiAssistantInformationRow,
} from '~/types/AiAssistantDetailPage'
import type { AssistantVideoBuildResult } from '~/types/AssistantSidecar'
import type { AtelierTool } from '~/types/AtelierToolSheet'
import type {
  UseAtelierToolSheetReturn,
  UseCopyToClipboardReturn,
  UseOpenExternalUrlReturn,
  UseToastReturn,
  UseVideoGenerationChecksReturn,
} from '~/types/Composables'
import type { DemoSitePreviewDeviceOption } from '~/types/DemoSiteDetailPage'
import type { AssistantMutationNotice, AssistantRequestMutationNotice } from '~/types/DrawerStack'
import type { TemplatePreviewDevice } from '~/types/TemplatePicker'
import type { UiConfirmModalHandle } from '~/types/UiConfirmModal'
import { computed, onMounted, ref, watch } from 'vue'
import AssistantFaqCard from '~/components/ai-assistants/AssistantFaqCard.vue'
import AtelierDevicePreview from '~/components/atelier/DevicePreview.vue'
import AssistantInstallGuideCard from '~/components/ai-assistants/AssistantInstallGuideCard.vue'
import AssistantPortrait from '~/components/ai-assistants/AssistantPortrait.vue'
import AssistantRecentRequests from '~/components/ai-assistants/AssistantRecentRequests.vue'
import AssistantSettingsForm from '~/components/ai-assistants/AssistantSettingsForm.vue'
import AssistantSubscriptionCard from '~/components/ai-assistants/AssistantSubscriptionCard.vue'
import AssistantVideoCard from '~/components/ai-assistants/AssistantVideoCard.vue'
import { useAtelierToolSheet } from '~/composables/useAtelierToolSheet'
import { useCoarsePointer } from '~/composables/useCoarsePointer'
import { useToast } from '~/composables/useToast'
import { useVideoGenerationChecks } from '~/composables/useVideoGenerationChecks'
import { useVideoGenerationProgress } from '~/composables/useVideoGenerationProgress'
import { RECEPTIONIST_VIDEO_BUILD_PHASES } from '~/constants/videoBuildPhases'
import { AiAssistantService } from '~/services/aiAssistantService'
import { AssistantSidecarService } from '~/services/assistantSidecarService'
import { useDrawerStackStore } from '~/stores/drawerStack'
import {
  assistantLanguagesLabel,
  assistantLifetimeLabel,
  demoUrlWithInternal,
  mailboxStatusLabel,
  missingStartStepsLabel,
} from '~/utils/aiAssistantLabels'
import { assistantPortraitUrl, shownOwnImageBackground, shownOwnImageUrl } from '~/utils/assistantPortrait'
import { ClipboardCopy } from '~/utils/clipboardCopy'
import { daysUntil, formatNumericDate } from '~/utils/date'

definePageMeta({ layout: 'dashboard', middleware: ['auth', 'ai-assistant-module'], shouldFillDashboardViewport: true })

/** The tools of the atelier, in the order of the bottom bar. */
const atelierTools: AtelierTool<AiAssistantAtelierToolKey>[] = [
  {
    key: 'identite',
    label: 'Identité',
    icon: 'i-lucide-user-round',
    title: 'Identité',
    hint: 'Prénom, visage, ton, langues, couleur : la page change en direct.',
  },
  {
    key: 'reponses',
    label: 'Réponses',
    icon: 'i-lucide-message-circle-question',
    title: 'Réponses',
    hint: 'Ce que les visiteurs ont demandé sans réponse, et les réponses en place.',
  },
  {
    key: 'demandes',
    label: 'Demandes',
    icon: 'i-lucide-inbox',
    title: 'Demandes',
    hint: 'Ce que les visiteurs ont laissé : devis, rendez-vous, questions.',
  },
  {
    key: 'alertes',
    label: 'Alertes',
    icon: 'i-lucide-bell-ring',
    title: 'Alertes au commerçant',
    hint: 'Email, SMS immédiat, heures calmes, boîte mail, modèle.',
  },
  {
    key: 'video',
    label: 'Vidéo',
    icon: 'i-lucide-clapperboard',
    title: 'Vidéo de prospection',
    hint: 'La vidéo envoyée dans les emails et les SMS.',
  },
  {
    key: 'plus',
    label: 'Plus',
    icon: 'i-lucide-ellipsis',
    title: 'Lien, client et après-vente',
    hint: "Le lien, le script, l'espace du client, l'abonnement, les informations.",
  },
]

/** The tools that open a page of their own: they have no need of the receptionist's page in sight. */
const PAGE_TOOL_KEYS: AiAssistantAtelierToolKey[] = ['reponses', 'demandes', 'alertes', 'video', 'plus']

/** The two ways of looking at the page. */
const previewDevices: DemoSitePreviewDeviceOption[] = [
  { key: 'mobile', label: 'Téléphone', icon: 'i-lucide-smartphone' },
  { key: 'desktop', label: 'Ordinateur', icon: 'i-lucide-monitor' },
]

/** How many of the assistant's requests the page lists. */
const RECENT_REQUESTS_LIMIT: number = 6

/** Start of the API refusal to delete an assistant still paid for, shown as it is. */
const SUBSCRIPTION_STILL_PAID_REFUSAL: string = "Résiliez d'abord l'abonnement"

const route: ReturnType<typeof useRoute> = useRoute()
const router: ReturnType<typeof useRouter> = useRouter()
const toast: UseToastReturn = useToast()
const drawerStack: ReturnType<typeof useDrawerStackStore> = useDrawerStackStore()
const { openExternalUrl }: UseOpenExternalUrlReturn = useOpenExternalUrl()
const { copy, copied }: UseCopyToClipboardReturn = useCopyToClipboard()
const isCoarsePointer: Ref<boolean> = useCoarsePointer()
const {
  activeTool,
  sheetSize,
  workAreaElement,
  sheetElement,
  isToolSheetOpen,
  activeToolMeta,
  activeToolHint,
  sheetStyle,
  toggleTool,
  closeActiveTool,
  registerToolButton,
  startSheetDrag,
  followSheetDrag,
  endSheetDrag,
  cancelSheetDrag,
  toggleSheetSize,
}: UseAtelierToolSheetReturn<AiAssistantAtelierToolKey> = useAtelierToolSheet<AiAssistantAtelierToolKey>(
  atelierTools,
  PAGE_TOOL_KEYS,
  isCoarsePointer,
)
const videoProgress: UseVideoGenerationProgressReturn = useVideoGenerationProgress(RECEPTIONIST_VIDEO_BUILD_PHASES)
const {
  isTakingLongerThanExpected: isVideoTakingLongerThanExpected,
  startChecks: startVideoGenerationChecks,
  checkNow: checkVideoGenerationNow,
}: UseVideoGenerationChecksReturn = useVideoGenerationChecks(refreshAssistant, (): boolean => isVideoGenerating.value)

const assistant: Ref<AiAssistantSummary | null> = ref(null)
const requests: Ref<AiAssistantRequestItem[]> = ref([])
const pendingRequestCount: Ref<number> = ref(0)
const pending: Ref<boolean> = ref(true)
const loadError: Ref<string | null> = ref(null)
const previewDevice: Ref<TemplatePreviewDevice> = ref('mobile')
/** Bumped after each save so the preview reloads the published receptionist. */
const previewReloadNonce: Ref<number> = ref(0)
/** The identity as it is being typed, pushed live into the page before it is published. */
const identityDraft: Ref<AiAssistantEditForm | null> = ref(null)
/** The identity form, in the sheet under the live page. */
const identityForm: Ref<InstanceType<typeof AssistantSettingsForm> | null> = ref(null)
/** The alerts form, on its own page. */
const alertsForm: Ref<InstanceType<typeof AssistantSettingsForm> | null> = ref(null)
const isPublishing: Ref<boolean> = ref(false)
const isSnippetCopied: Ref<boolean> = ref(false)
const isRegenerating: Ref<boolean> = ref(false)
const isDeleting: Ref<boolean> = ref(false)
const isSendingClientLink: Ref<boolean> = ref(false)
const isRevokingClientLinks: Ref<boolean> = ref(false)
const clientSpaceLinkForManualCopy: Ref<string | null> = ref(null)
const isMarkingSold: Ref<boolean> = ref(false)
const isVideoBusy: Ref<boolean> = ref(false)
const isRemovingVideo: Ref<boolean> = ref(false)
const isRefreshingVideo: Ref<boolean> = ref(false)
const deleteConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const clientSpaceConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const revokeLinksConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const newClientLinkConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const soldConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)
const videoDeleteConfirmModal: Ref<UiConfirmModalHandle | null> = ref(null)

const assistantId: ComputedRef<number> = computed((): number => Number(route.params.id))

const pageTitle: ComputedRef<string> = computed(
  (): string => `${assistant.value?.business_name ?? 'Réceptionniste IA'} — DevLeadHunter`,
)

const portraitUrl: ComputedRef<string> = computed((): string =>
  assistant.value
    ? assistantPortraitUrl(
        assistant.value.demo_url,
        assistant.value.assistant_name,
        assistant.value.assistant_gender,
        shownOwnImageUrl(assistant.value),
      )
    : '',
)

const demoUrl: ComputedRef<string> = computed((): string =>
  assistant.value ? demoUrlWithInternal(assistant.value.demo_url) : '',
)

const isSold: ComputedRef<boolean> = computed((): boolean => assistant.value?.status === 'delivered')

/** Where the receptionist stands: waiting for her first send, counting down, sold. */
const lifetimeLabel: ComputedRef<string> = computed((): string =>
  assistant.value ? assistantLifetimeLabel(assistant.value) : '',
)

const statusPillClass: ComputedRef<string> = computed((): string => {
  if (isSold.value) return 'bg-[var(--app-ink)] text-[var(--app-bg)]'
  if (assistant.value?.status === 'active') return 'bg-[var(--app-green)]/20 text-[var(--app-green)]'
  if (assistant.value?.status === 'failed') return 'bg-[var(--app-red)]/20 text-[var(--app-red)]'
  return 'bg-[var(--app-surface-2)] text-[var(--app-ink-soft)]'
})

const isVideoGenerating: ComputedRef<boolean> = computed(
  (): boolean => assistant.value?.video_status === 'pending' || assistant.value?.video_status === 'generating',
)

/** One line under the name: who she is, what she captured over 30 days, the video or the client's site. */
const assistantFactsLine: ComputedRef<string> = computed((): string => {
  if (!assistant.value) return ''
  const facts: string[] = [
    `${assistant.value.assistant_name} · ${assistantLanguagesLabel(assistant.value.languages)}`,
    `${assistant.value.conversations_30d} conv. et ${assistant.value.requests_30d} demandes sur 30 j`,
  ]
  if (isSold.value) {
    facts.push(
      assistant.value.installed_host ? `Bulle vue sur ${assistant.value.installed_host}` : 'Bulle pas encore vue',
    )
  } else {
    facts.push(
      assistant.value.video_status === 'ready'
        ? 'Vidéo prête'
        : isVideoGenerating.value
          ? 'Vidéo en cours'
          : 'Pas de vidéo',
    )
  }
  return facts.join(' · ')
})

/** Under the link: when the demo goes offline, or what the page is for once sold. */
const demoLinkHint: ComputedRef<string> = computed((): string => {
  if (!assistant.value) return ''
  if (isSold.value) return 'La page des clients du commerce : questions, photos, devis et rendez-vous.'
  if (!assistant.value.demo_link_sent_at || !assistant.value.expires_at) {
    return 'Le lien envoyé au prospect. Le compte à rebours démarre au premier email envoyé.'
  }
  const days: number = daysUntil(assistant.value.expires_at)
  return `Le lien envoyé au prospect. La démo est retirée dans ${days} jour${days > 1 ? 's' : ''}, le ${formatNumericDate(assistant.value.expires_at)}.`
})

const conversationsLabel: ComputedRef<string> = computed((): string => {
  if (!assistant.value) return ''
  const count: number = assistant.value.conversations_30d
  if (count === 0) return 'Aucune conversation sur les 30 derniers jours.'
  return `${count} conversation${count > 1 ? 's' : ''} sur les 30 derniers jours, ${assistant.value.conversations_7d} cette semaine.`
})

/** The four counters of the assistant, tests excluded. */
const stats: ComputedRef<AiAssistantDetailStat[]> = computed((): AiAssistantDetailStat[] => {
  if (!assistant.value) return []
  const outside: string =
    assistant.value.requests_outside_hours_pct === null ? '—' : `${assistant.value.requests_outside_hours_pct} %`
  return [
    { label: 'Conversations · 7 j', value: assistant.value.conversations_7d, icon: 'i-lucide-messages-square' },
    { label: 'Conversations · 30 j', value: assistant.value.conversations_30d, icon: 'i-lucide-messages-square' },
    { label: 'Demandes · 30 j', value: assistant.value.requests_30d, icon: 'i-lucide-inbox' },
    { label: 'Hors horaires', value: outside, icon: 'i-lucide-moon' },
  ]
})

/** The facts of the « Plus » page, as the summary listed them. */
const informationRows: ComputedRef<AiAssistantInformationRow[]> = computed((): AiAssistantInformationRow[] => {
  const current: AiAssistantSummary | null = assistant.value
  if (!current) return []
  const rows: AiAssistantInformationRow[] = [
    { label: 'Statut', value: lifetimeLabel.value },
    { label: 'Prénom', value: current.assistant_name },
    { label: 'Langues', value: assistantLanguagesLabel(current.languages) },
    { label: 'Ton', value: current.tone ?? 'Par défaut' },
    { label: 'Couleur', value: current.accent_color ?? 'Neutre' },
    { label: 'Email du commerçant', value: current.email ?? 'Aucun' },
    { label: "Mobile d'alerte", value: current.alerts.phone ?? 'Aucun' },
  ]
  if (isSold.value) {
    rows.push({
      label: 'Sur son site',
      value: current.installed_host
        ? `${current.installed_host}${current.installed_at ? ` · vue le ${formatNumericDate(current.installed_at)}` : ''}`
        : 'Bulle pas encore vue',
    })
    rows.push({
      label: 'Fiche Google',
      value: current.google_profile_linked_at
        ? `Adresse posée le ${formatNumericDate(current.google_profile_linked_at)}`
        : 'Adresse pas encore posée',
    })
  }
  rows.push({ label: 'Boîte mail', value: mailboxStatusLabel(current) })
  rows.push({ label: 'Modèle', value: current.eu_only ? 'IA hébergée en Europe' : 'Mistral, secours Groq' })
  rows.push({ label: 'Créée le', value: formatNumericDate(current.created_at) })
  return rows
})

/** The live page stands, with or without the identity sheet; a page tool takes its place. */
const isPreviewShown: ComputedRef<boolean> = computed(
  (): boolean => activeTool.value === null || !PAGE_TOOL_KEYS.includes(activeTool.value),
)

const isPageToolOpen: ComputedRef<boolean> = computed(
  (): boolean => activeTool.value !== null && PAGE_TOOL_KEYS.includes(activeTool.value),
)

/** The two forms that may hold an unsaved edit, once rendered. */
const settingsForms: ComputedRef<InstanceType<typeof AssistantSettingsForm>[]> = computed(
  (): InstanceType<typeof AssistantSettingsForm>[] =>
    [identityForm.value, alertsForm.value].filter(
      (form: InstanceType<typeof AssistantSettingsForm> | null): form is InstanceType<typeof AssistantSettingsForm> =>
        form !== null,
    ),
)

/** Any unsaved edit: « Annuler » and « Publier » take the place of the link buttons in the top bar. */
const hasPendingChanges: ComputedRef<boolean> = computed((): boolean =>
  settingsForms.value.some((form: InstanceType<typeof AssistantSettingsForm>): boolean => form.hasChanges),
)

/** Which tools hold an unpublished change, for the dot on their button. */
const toolPendingChanges: ComputedRef<Record<AiAssistantAtelierToolKey, boolean>> = computed(
  (): Record<AiAssistantAtelierToolKey, boolean> => ({
    identite: identityForm.value?.changedSections.identity ?? false,
    reponses: false,
    demandes: false,
    alertes: alertsForm.value?.changedSections.alerts ?? false,
    video: false,
    plus: false,
  }),
)

/** What waits on each tool: questions without an answer, requests to handle. */
const toolWaitingCounts: ComputedRef<Partial<Record<AiAssistantAtelierToolKey, number>>> = computed(
  (): Partial<Record<AiAssistantAtelierToolKey, number>> => ({
    reponses: assistant.value?.unanswered_count || undefined,
    demandes: pendingRequestCount.value || undefined,
  }),
)

/** The identity edits pushed live into the page, only while something is unpublished. */
const previewMessage: ComputedRef<Record<string, unknown> | null> = computed((): Record<string, unknown> | null => {
  if (!identityDraft.value || !toolPendingChanges.value.identite) return null
  return {
    assistant_name: identityDraft.value.assistant_name,
    business_name: identityDraft.value.business_name,
    accent_color: identityDraft.value.accent_color,
  }
})

const businessRecipientLabel: ComputedRef<string> = computed((): string =>
  assistant.value?.email ? `à ${assistant.value.email}` : "à l'adresse connue du commerce",
)

const clientSpaceConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Envoyer au commerçant ${businessRecipientLabel.value} le lien de son espace (demandes, rapport, réglages, abonnement) ? Le lien est aussi copié.`,
)

const deleteConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Supprimer la réceptionniste de « ${assistant.value?.business_name ?? ''} » ? Sa démo et son widget s'arrêtent. Sont effacés : ses documents, ses conversations, les demandes et les photos des visiteurs, les rendez-vous, les rapports, l'agenda connecté et la vidéo. Les ventes et les abonnements passés restent.`,
)

const newClientLinkConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Les liens déjà envoyés ne s'ouvrent plus. Envoyer ${businessRecipientLabel.value} un nouveau lien de son espace ? Le lien est aussi copié.`,
)

const soldConfirmMessage: ComputedRef<string> = computed(
  (): string =>
    `Marquer la réceptionniste de « ${assistant.value?.business_name ?? ''} » comme vendue hors Stripe (virement, votre propre entreprise) ? Elle n'expire plus, chaque demande alerte le commerçant par e-mail et SMS, et l'entreprise reçoit son e-mail de bienvenue avec l'espace client.`,
)

useSeoMeta({ title: pageTitle })

/** Open the journal of what the visitors asked. */
function openConversations(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-conversations', assistant: assistant.value })
}

/** Open what the assistant reads: website, Google listing, documents. */
function openSources(): void {
  if (assistant.value) drawerStack.push({ kind: 'assistant-sources', assistant: assistant.value })
}

/**
 * Keep the identity as it is typed, for the live preview.
 * @param edited - The form as it stands.
 */
function onDraftChange(edited: AiAssistantEditForm): void {
  identityDraft.value = edited
}

/**
 * The settings were saved: show the assistant as the API returned it, everywhere, preview included.
 * @param updated - The assistant as the API returned it.
 */
function onAssistantSaved(updated: AiAssistantSummary): void {
  assistant.value = updated
  drawerStack.notifyAssistantUpdated(updated)
  previewReloadNonce.value += 1
}

/**
 * Publish the unsaved identity and alert edits in one save.
 * @returns A promise resolved once saved or refused.
 */
async function publishPendingChanges(): Promise<void> {
  if (isPublishing.value) return
  isPublishing.value = true
  try {
    for (const form of settingsForms.value) {
      if (form.hasChanges) await form.save()
    }
  } finally {
    isPublishing.value = false
  }
}

/**
 * Drop every unsaved edit: the form and the page go back to the published receptionist.
 */
function resetPendingChanges(): void {
  for (const form of settingsForms.value) form.reset()
}

/**
 * Copy the script to paste on the client's site.
 * @returns A promise resolved once copied (or refused).
 */
async function copySnippet(): Promise<void> {
  if (!assistant.value) return
  isSnippetCopied.value = await ClipboardCopy.copyText(assistant.value.embed_snippet)
  if (!isSnippetCopied.value) {
    toast.error('Copie impossible : sélectionnez le script et copiez-le.')
    return
  }
  setTimeout((): void => {
    isSnippetCopied.value = false
  }, 2_000)
}

/**
 * Open a request in its drawer.
 * @param request - The request.
 */
function openRequest(request: AiAssistantRequestItem): void {
  drawerStack.push({ kind: 'assistant-request', request })
}

/**
 * Rebuild the assistant's knowledge from its prospect's latest data, keeping its branding and link.
 * @returns A promise resolved once regenerated.
 */
async function regenerateAssistant(): Promise<void> {
  if (!assistant.value || isRegenerating.value) return
  isRegenerating.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.regenerate(assistant.value.id)
    assistant.value = updated
    drawerStack.notifyAssistantUpdated(updated)
    previewReloadNonce.value += 1
    toast.success('Réceptionniste régénérée depuis les dernières données du prospect.')
  } catch {
    toast.error('Régénération impossible pour le moment.')
  } finally {
    isRegenerating.value = false
  }
}

/**
 * Mark the assistant sold outside Stripe: served for good, its owner alerted, the business welcomed.
 * @returns A promise resolved once marked (or refused).
 */
async function markSold(): Promise<void> {
  if (!assistant.value || isMarkingSold.value) return
  isMarkingSold.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.markSold(assistant.value.id)
    assistant.value = updated
    drawerStack.notifyAssistantUpdated(updated)
    toast.success("Réceptionniste marquée vendue : elle alerte le commerçant et l'e-mail de bienvenue est parti.")
  } catch {
    toast.error('Impossible de marquer cette réceptionniste vendue pour le moment.')
  } finally {
    isMarkingSold.value = false
  }
}

/**
 * Email the business its client-space link and copy it.
 * @returns A promise resolved once sent (or refused).
 */
async function sendClientSpace(): Promise<void> {
  if (!assistant.value) return
  isSendingClientLink.value = true
  clientSpaceLinkForManualCopy.value = null
  const linkRequest: Promise<AiAssistantClientLink> = AiAssistantService.issueClientLink(assistant.value.id, true)
  const copyAttempt: Promise<boolean> = ClipboardCopy.copyWhenReady(
    linkRequest.then((link: AiAssistantClientLink): string => link.url),
  )
  try {
    const link: AiAssistantClientLink = await linkRequest
    const isCopied: boolean = await copyAttempt
    const copyNote: string = isCopied ? ' Lien copié.' : ' Lien non copié : copiez-le dans Plus.'
    if (!isCopied) clientSpaceLinkForManualCopy.value = link.url
    if (link.sent_to) {
      toast.success(`Espace client envoyé à ${link.sent_to}.${copyNote}`)
    } else {
      toast.error(`Email non envoyé : ${(link.send_error ?? 'raison inconnue').replace(/\.+$/, '')}.${copyNote}`)
    }
  } catch {
    toast.error("Lien de l'espace client indisponible pour l'instant.")
  } finally {
    isSendingClientLink.value = false
  }
}

/**
 * Stop every client-space link sent so far, then offer to send the business a new one.
 * @returns A promise resolved once the links are cut (or the cut refused).
 */
async function revokeClientLinks(): Promise<void> {
  if (!assistant.value || isRevokingClientLinks.value) return
  isRevokingClientLinks.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.revokeClientLinks(assistant.value.id)
    assistant.value = updated
    clientSpaceLinkForManualCopy.value = null
    drawerStack.notifyAssistantUpdated(updated)
    newClientLinkConfirmModal.value?.open()
  } catch {
    toast.error('Impossible de couper les liens pour le moment.')
  } finally {
    isRevokingClientLinks.value = false
  }
}

/**
 * Delete the assistant (its files and its visitors' data are erased) and go back to the list.
 * @returns A promise resolved once removed (or refused).
 */
async function removeAssistant(): Promise<void> {
  if (!assistant.value || isDeleting.value) return
  isDeleting.value = true
  try {
    await AiAssistantService.remove(assistant.value.id)
    drawerStack.notifyAssistantDeleted(assistant.value.id)
    toast.success('Réceptionniste supprimée, ses fichiers et les données de ses visiteurs sont effacés.')
    await router.push('/dashboard/ai-assistants')
  } catch (error: unknown) {
    const detail: string = error instanceof Error ? error.message : ''
    toast.error(detail.startsWith(SUBSCRIPTION_STILL_PAID_REFUSAL) ? detail : "Suppression impossible pour l'instant.")
  } finally {
    isDeleting.value = false
  }
}

/**
 * Start (or restart) the prospection video: on the desktop app first, on the server otherwise.
 * @returns A promise resolved once the generation is requested.
 */
async function generateVideo(): Promise<void> {
  if (!assistant.value || isVideoBusy.value) return
  isVideoBusy.value = true
  videoProgress.start(assistant.value.slug, 'Publication de la vidéo')
  try {
    const build: AssistantVideoBuildResult = await AssistantSidecarService.buildFullVideo(assistant.value.id)
    if (build.status === 'done' && build.assistant) {
      videoProgress.finish()
      assistant.value = build.assistant
      videoProgress.close()
      toast.success('Vidéo générée sur votre ordinateur.')
      return
    }
    if (build.status === 'unavailable') {
      videoProgress.close()
    } else {
      // The window stays open with the error and its log, and says the server takes over.
      videoProgress.fail(build.message ?? 'Échec de la génération locale.')
      videoProgress.note('Bascule sur le serveur…')
    }
    assistant.value = await AiAssistantService.generateVideo(assistant.value.id)
    startVideoGenerationChecks()
    videoProgress.note('Montage lancé sur le serveur, suivi dans l’outil « Vidéo ».')
    toast.success('Génération de la vidéo lancée.')
  } catch (error: unknown) {
    const message: string = error instanceof Error ? error.message : 'Échec du lancement de la génération.'
    videoProgress.fail(message)
    toast.error(message)
  } finally {
    isVideoBusy.value = false
  }
}

/**
 * Delete the prospection video: its files, its link and its state.
 * @returns A promise resolved once deleted (or refused).
 */
async function removeVideo(): Promise<void> {
  if (!assistant.value || isRemovingVideo.value) return
  isRemovingVideo.value = true
  try {
    const updated: AiAssistantSummary = await AiAssistantService.clearVideo(assistant.value.id)
    assistant.value = updated
    drawerStack.notifyAssistantUpdated(updated)
    toast.success('Vidéo supprimée.')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Suppression de la vidéo impossible.')
  } finally {
    isRemovingVideo.value = false
  }
}

/**
 * Reload the video status on demand.
 * @returns A promise resolved once reloaded (or refused).
 */
async function refreshVideoStatusNow(): Promise<void> {
  if (isRefreshingVideo.value) return
  isRefreshingVideo.value = true
  try {
    await checkVideoGenerationNow()
  } catch {
    toast.error('Actualisation impossible pour le moment.')
  } finally {
    isRefreshingVideo.value = false
  }
}

/**
 * Refresh the assistant alone (video progress), leaving the page as it is.
 * @returns A promise resolved once refreshed.
 * @throws When the assistant cannot be reloaded.
 */
async function refreshAssistant(): Promise<void> {
  assistant.value = await AiAssistantService.get(assistantId.value)
}

/**
 * Load the assistant and its latest requests.
 * @returns A promise resolved once loaded.
 */
async function loadData(): Promise<void> {
  pending.value = true
  loadError.value = null
  try {
    const [loaded, requestList]: [AiAssistantSummary, AiAssistantRequestsResponse] = await Promise.all([
      AiAssistantService.get(assistantId.value),
      AiAssistantService.listRequests(undefined, assistantId.value),
    ])
    assistant.value = loaded
    requests.value = requestList.requests.slice(0, RECENT_REQUESTS_LIMIT)
    pendingRequestCount.value = requestList.pending_count
  } catch {
    loadError.value = 'Réceptionniste introuvable ou indisponible pour le moment.'
  } finally {
    pending.value = false
  }
}

watch(
  (): number => drawerStack.assistantMutationCounter,
  (): void => {
    const notice: AssistantMutationNotice | null = drawerStack.lastAssistantMutation
    if (notice?.type === 'updated' && notice.assistant.id === assistantId.value) assistant.value = notice.assistant
  },
)

watch(
  (): number => drawerStack.requestMutationCounter,
  (): void => {
    const notice: AssistantRequestMutationNotice | null = drawerStack.lastRequestMutation
    if (notice?.type !== 'updated') return
    requests.value = requests.value.map(
      (listedRequest: AiAssistantRequestItem): AiAssistantRequestItem =>
        listedRequest.id === notice.request.id ? notice.request : listedRequest,
    )
    pendingRequestCount.value = requests.value.filter(
      (listedRequest: AiAssistantRequestItem): boolean => listedRequest.status === 'new',
    ).length
  },
)

onMounted(async (): Promise<void> => {
  await loadData()
  if (isVideoGenerating.value) startVideoGenerationChecks()
})
</script>

<style scoped>
.atelier-sheet-enter-active,
.atelier-sheet-leave-active {
  transition:
    transform 0.22s ease,
    opacity 0.22s ease;
}
.atelier-sheet-enter-from,
.atelier-sheet-leave-to {
  transform: translateY(24px);
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .atelier-sheet-enter-active,
  .atelier-sheet-leave-active {
    transition: none;
  }
}
</style>
