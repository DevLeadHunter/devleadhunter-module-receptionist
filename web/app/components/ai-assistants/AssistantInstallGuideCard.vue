<template>
  <UiCollapsibleCard icon="i-lucide-code-2" title="Installer sur le site du client" suffix="WordPress, Wix, Shopify…">
    <div class="space-y-4 px-4 py-4">
      <p class="text-sm text-[var(--app-ink-soft)]">
        Une ligne à coller une fois, sur le gabarit commun à toutes les pages. Choisissez la plateforme du client.
      </p>

      <UiFilterTabs v-model="platformKey" :tabs="tabs" />

      <ol class="list-decimal space-y-2 pl-5 text-sm text-[var(--app-ink)]">
        <li v-for="step in guide.steps" :key="step">{{ step }}</li>
      </ol>
      <p v-if="guide.note" class="text-xs text-[var(--app-ink-soft)]">{{ guide.note }}</p>

      <div class="space-y-2">
        <pre
          class="overflow-x-auto rounded-lg border border-[var(--app-line)] bg-[var(--app-surface-2)] px-3 py-2.5 font-mono text-[11px] leading-relaxed break-all whitespace-pre-wrap text-[var(--app-ink)]"
          >{{ props.embedSnippet }}</pre
        >
        <button
          type="button"
          class="btn-secondary inline-flex h-9 items-center gap-2 px-4 text-xs"
          @click="copySnippet"
        >
          <UIcon name="i-lucide-copy" class="h-3.5 w-3.5" />
          {{ copied ? 'Copié !' : 'Copier le script' }}
        </button>
      </div>
    </div>
  </UiCollapsibleCard>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import { computed, ref } from 'vue'
import type { AssistantInstallGuide, AssistantInstallGuideCardProps } from '~/types/AssistantInstallGuideCard'
import type { UseCopyToClipboardReturn } from '~/types/Composables'
import type { UiFilterTab } from '~/types/UiFilterTabs'
import { useCopyToClipboard } from '~/composables/useCopyToClipboard'
import { ASSISTANT_INSTALL_GUIDES } from '~/constants/assistantInstallGuides'

/** Where to paste the widget's script, platform by platform, with the script itself and a copy button. */
const props: AssistantInstallGuideCardProps = defineProps({
  embedSnippet: {
    type: String,
    required: true,
  },
})

const { copy, copied }: UseCopyToClipboardReturn = useCopyToClipboard()

const platformKey: Ref<string> = ref(ASSISTANT_INSTALL_GUIDES[0]?.key ?? 'html')

const tabs: ComputedRef<UiFilterTab[]> = computed((): UiFilterTab[] =>
  ASSISTANT_INSTALL_GUIDES.map((guide: AssistantInstallGuide): UiFilterTab => ({ key: guide.key, label: guide.label })),
)

const guide: ComputedRef<AssistantInstallGuide> = computed(
  (): AssistantInstallGuide =>
    ASSISTANT_INSTALL_GUIDES.find((candidate: AssistantInstallGuide): boolean => candidate.key === platformKey.value) ??
    ASSISTANT_INSTALL_GUIDES[ASSISTANT_INSTALL_GUIDES.length - 1] ?? {
      key: 'html',
      label: 'Autre',
      steps: [],
      note: null,
    },
)

/**
 * Copy the script line to the clipboard.
 * @returns A promise resolved once copied.
 */
async function copySnippet(): Promise<void> {
  await copy(props.embedSnippet)
}
</script>
