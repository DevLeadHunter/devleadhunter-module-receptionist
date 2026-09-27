<template>
  <div class="cs-report">
    <template v-if="!props.report">
      <p class="cs-sec">Rapport du mois</p>
      <div class="cs-block">
        <p class="cs-text cs-text--dim">
          Le premier rapport de {{ props.assistantName }} arrive au début du mois prochain, par email et ici.
        </p>
      </div>
    </template>
    <template v-else>
      <p class="cs-sec">{{ props.report.month_label }}</p>
      <div class="cs-block cs-stats">
        <div v-for="figure in figures" :key="figure.label" class="cs-stat">
          <span
            ><b>{{ figure.value }}</b
            ><span>{{ figure.label }}</span></span
          >
        </div>
      </div>
      <div v-if="props.report.languages_line || props.report.handling_line" class="cs-block cs-report__lines">
        <p v-if="props.report.languages_line" class="cs-text">
          Langues des conversations : {{ props.report.languages_line }}.
        </p>
        <p v-if="props.report.handling_line" class="cs-text">{{ props.report.handling_line }}</p>
      </div>
      <template v-if="props.report.top_questions.length > 0">
        <p class="cs-sec">Ce que vos visiteurs demandent le plus</p>
        <div class="cs-block">
          <ol class="cs-report__questions">
            <li v-for="question in props.report.top_questions" :key="question">{{ question }}</li>
          </ol>
        </div>
      </template>
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import { computed } from 'vue'
import type { AiAssistantClientReport } from '~/types/AiAssistantClientSpace'
import type { ClientSpaceReportFigure, ClientSpaceReportProps } from '~/types/ClientSpaceReport'

/**
 * The latest monthly report of the client's receptionist: its figures, languages and most asked questions.
 * @param report The latest report, or null before the first one.
 * @param assistantName The receptionist's first name, for the waiting message.
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
.cs-report {
  display: grid;
  align-content: start;
}

.cs-report__lines {
  margin-top: 10px;
}

.cs-report__questions {
  margin: 0;
  padding: 14px 16px 14px 36px;
  font-size: 15px;
  line-height: 1.6;
}
</style>
