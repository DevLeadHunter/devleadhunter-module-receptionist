import type { ProspectSearchWaveOptions } from '~/types/ProspectSearchCreatePage'
import type { SourcingVertical } from '~/types/Sourcing'
import { SourcingService } from '~/services/sourcingService'

/** The receptionist's target verticals, offered as trade chips wave by wave in a new prospect search. */
export class AssistantTradeWaves {
  /**
   * Load the target verticals and group their search terms by wave.
   * @returns The waves, wave 1 first.
   */
  static async load(): Promise<ProspectSearchWaveOptions[]> {
    const verticals: SourcingVertical[] = await SourcingService.listVerticals()
    const wavesByNumber: Map<number, ProspectSearchWaveOptions> = new Map()
    for (const vertical of verticals) {
      const wave: ProspectSearchWaveOptions = wavesByNumber.get(vertical.wave) ?? {
        wave: vertical.wave,
        labels: [],
        options: [],
      }
      wave.labels.push(vertical.label)
      for (const searchTerm of vertical.search_terms) {
        wave.options.push({ value: searchTerm, label: searchTerm })
      }
      wavesByNumber.set(vertical.wave, wave)
    }
    return [...wavesByNumber.values()].sort(
      (firstWave: ProspectSearchWaveOptions, secondWave: ProspectSearchWaveOptions): number =>
        firstWave.wave - secondWave.wave,
    )
  }
}
