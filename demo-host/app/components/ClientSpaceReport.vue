<template>
  <ClientSpaceSection title="Rapport du mois" :meta="report ? report.month_label : null">
    <p v-if="!report" class="cs-muted">
      Le premier rapport de {{ assistantName }} arrive au début du mois prochain, par email et ici.
    </p>
    <template v-else>
      <ul class="csp__grid">
        <li v-for="figure in figures" :key="figure.label" class="csp__figure">
          <span class="csp__value">{{ figure.value }}</span>
          <span class="csp__label">{{ figure.label }}</span>
        </li>
      </ul>
      <p v-if="report.languages_line" class="csp__line">Langues des conversations : {{ report.languages_line }}.</p>
      <p v-if="report.handling_line" class="csp__line">{{ report.handling_line }}</p>
      <template v-if="report.top_questions.length > 0">
        <h3 class="csp__subtitle">Ce que vos visiteurs demandent le plus</h3>
        <ol class="csp__questions">
          <li v-for="question in report.top_questions" :key="question">{{ question }}</li>
        </ol>
      </template>
    </template>
  </ClientSpaceSection>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientReport } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceReportFigure, ClientSpaceReportProps } from '~/types/ClientSpaceReport'

/**
 * The latest monthly report of the client's assistant: its figures, languages and most asked questions.
 * @param report The latest report, or null before the first one.
 * @param assistantName The assistant's first name, for the waiting message.
 */
const props: ClientSpaceReportProps = defineProps({
  report: { type: Object as PropType<AiAssistantClientReport | null>, default: null },
  assistantName: { type: String, required: true },
})

const figures: ComputedRef<ClientSpaceReportFigure[]> = computed((): ClientSpaceReportFigure[] => {
  const report: AiAssistantClientReport | null = props.report
  if (!report) return []
  const shown: ClientSpaceReportFigure[] = [
    { value: String(report.conversations), label: plural(report.conversations, 'conversation') },
    { value: String(report.requests), label: plural(report.requests, 'demande') },
    { value: String(report.appointments), label: 'rendez-vous' },
    { value: String(report.quotes), label: 'devis' },
  ]
  if (report.photo_requests > 0) shown.push({ value: String(report.photo_requests), label: 'avec photo' })
  if (report.urgent > 0) shown.push({ value: String(report.urgent), label: plural(report.urgent, 'urgence') })
  if (report.outside_hours_pct !== null) shown.push({ value: `${report.outside_hours_pct} %`, label: 'hors horaires' })
  return shown
})

/**
 * A noun agreeing with a figure shown apart (« demande » under 1, « demandes » under 43).
 * @param value The figure.
 * @param noun The singular noun.
 * @returns The noun, plural above one.
 */
function plural(value: number, noun: string): string {
  return value > 1 ? `${noun}s` : noun
}
</script>

<style scoped>
.csp__grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
}

.csp__figure {
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1px solid var(--cs-line);
  border-top: 3px solid var(--a-accent);
  border-radius: 12px;
  background: var(--cs-card);
  padding: 12px 8px;
}

.csp__value {
  font-family: Fraunces, Georgia, serif;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.1;
}

.csp__label {
  margin-top: 2px;
  font-size: 12px;
  color: var(--cs-ink-dim);
}

.csp__line {
  margin: 14px 0 0;
  font-size: 14px;
  line-height: 1.5;
}

.csp__subtitle {
  margin: 20px 0 8px;
  font-size: 15px;
  font-weight: 600;
}

.csp__questions {
  margin: 0;
  padding-left: 22px;
  list-style: decimal;
  font-size: 14px;
  line-height: 1.6;
}
</style>
