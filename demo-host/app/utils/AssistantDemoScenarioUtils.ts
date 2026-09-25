import type { AssistantExampleLabels, AssistantWidgetLang } from '~/types/AiAssistant'
import type { AssistantLeadSummary } from '~/types/AssistantChat'
import type { AssistantDemoScriptStep } from '~/types/AssistantDemoScript'
import { EXAMPLE_LABELS, PHOTO_LABELS } from '~/constants/AssistantWidgetLabels'

type TradeExample = {
  /** Matched against the Google category once both are folded (lower case, no accents). */
  keywords: string[]
  need: string
  /** What the customer writes first when the demo page plays the conversation by itself. */
  opening: string
  kind: AssistantLeadSummary['kind']
  hasPhoto: boolean
  /** « samedi matin », empty when the example is not an appointment. */
  slots: string
}

const TRADE_EXAMPLES: TradeExample[] = [
  {
    keywords: ['couvreur', 'toiture', 'charpent', 'zingu'],
    need: 'fuite après la tempête, tuiles déplacées côté rue',
    opening:
      "Bonjour, j'ai une fuite depuis la tempête, des tuiles ont bougé côté rue. Vous pouvez passer cette semaine ?",
    kind: 'quote',
    hasPhoto: true,
    slots: '',
  },
  {
    keywords: ['plomb', 'chauffag', 'sanitaire'],
    need: "fuite sous l'évier de la cuisine, ça goutte",
    opening: "Bonjour, ça goutte sous l'évier de la cuisine depuis ce matin. Vous pouvez passer cette semaine ?",
    kind: 'quote',
    hasPhoto: true,
    slots: '',
  },
  {
    keywords: ['electric', 'électric'],
    need: 'plus de courant dans la cuisine, le tableau saute',
    opening: 'Bonjour, plus de courant dans la cuisine, le tableau saute dès que je le remonte. Vous pouvez venir ?',
    kind: 'question',
    hasPhoto: false,
    slots: '',
  },
  {
    keywords: ['carross', 'garage', 'mecani', 'mécani', 'automobile'],
    need: 'rayure sur la portière avant droite, devis carrosserie',
    opening: "Bonjour, j'ai une rayure sur la portière avant droite. Vous faites un devis carrosserie ?",
    kind: 'quote',
    hasPhoto: true,
    slots: '',
  },
  {
    keywords: ['paysag', 'jardin', 'espaces verts'],
    need: 'taille de haie sur 30 m et tonte, devis annuel',
    opening: "Bonjour, j'ai 30 m de haie à tailler et la pelouse à tondre. Vous faites un devis à l'année ?",
    kind: 'quote',
    hasPhoto: false,
    slots: '',
  },
  {
    keywords: ['macon', 'maçon', 'batiment', 'bâtiment', 'renov', 'rénov'],
    need: 'fissure sur le mur du garage, devis reprise',
    opening: 'Bonjour, une fissure est apparue sur le mur du garage. Vous pouvez passer voir pour un devis ?',
    kind: 'quote',
    hasPhoto: true,
    slots: '',
  },
  {
    keywords: ['menuis', 'fenetr', 'fenêtr'],
    need: 'fenêtre qui ferme mal, devis remplacement',
    opening: 'Bonjour, une fenêtre ferme mal, je voudrais un devis pour la remplacer.',
    kind: 'quote',
    hasPhoto: true,
    slots: '',
  },
  {
    keywords: ['peintre', 'peinture'],
    need: 'salon de 25 m² à repeindre',
    opening: "Bonjour, j'ai un salon de 25 m² à repeindre. Vous pouvez me faire un devis ?",
    kind: 'quote',
    hasPhoto: false,
    slots: '',
  },
  {
    keywords: ['serrur'],
    need: "porte claquée, clés à l'intérieur",
    opening: "Bonjour, ma porte a claqué, les clés sont à l'intérieur. Vous pouvez venir vite ?",
    kind: 'question',
    hasPhoto: false,
    slots: '',
  },
  {
    keywords: ['coiff', 'barbier'],
    need: 'coupe et barbe',
    opening: "Bonjour, je voudrais une coupe et la barbe samedi matin, c'est possible ?",
    kind: 'appointment',
    hasPhoto: false,
    slots: 'samedi matin',
  },
  {
    keywords: ['restaurant', 'traiteur', 'pizz', 'brasserie'],
    need: 'table pour 6, un menu sans gluten',
    opening: "Bonsoir, une table pour 6 samedi soir, avec un menu sans gluten, c'est possible ?",
    kind: 'appointment',
    hasPhoto: false,
    slots: 'samedi soir',
  },
  {
    keywords: ['dentist', 'ostéo', 'osteo', 'kiné', 'kine'],
    need: 'douleur depuis hier, premier rendez-vous possible',
    opening: "Bonjour, j'ai une douleur depuis hier, vous auriez un premier rendez-vous rapidement ?",
    kind: 'appointment',
    hasPhoto: false,
    slots: '',
  },
  {
    keywords: ['immobil'],
    need: 'estimation de la maison avant mise en vente',
    opening: 'Bonjour, je voudrais une estimation de ma maison avant de la mettre en vente.',
    kind: 'question',
    hasPhoto: false,
    slots: '',
  },
]

const DEFAULT_EXAMPLE: TradeExample = {
  keywords: [],
  need: 'rappel souhaité en journée',
  opening: "Bonjour, j'aurais besoin d'un devis. Vous pouvez me rappeler dans la journée ?",
  kind: 'quote',
  hasPhoto: false,
  slots: '',
}

/** The customer of the example, the same for every trade. */
const EXAMPLE_NAME: string = 'Claire Martin'
const EXAMPLE_CONTACT: string = '06 12 34 56 78'

/**
 * The scene of the demo page: what a customer of this trade asks, and what the business receives.
 */
export class AssistantDemoScenarioUtils {
  /**
   * The trade as a customer would type it in Google (« couvreur »), from the Google category.
   * @param tradeLabel - The Google Maps category, or null.
   * @returns The lower-case trade, or « artisan » when unknown.
   */
  static searchWord(tradeLabel: string | null): string {
    const trade: string = (tradeLabel ?? '').trim().toLowerCase()
    return trade || 'artisan'
  }

  /**
   * The example request of the trade, shown on the business's phone until a real one comes in.
   * @param tradeLabel - The Google Maps category, or null.
   * @returns The example, as the alert would summarise it.
   */
  static example(tradeLabel: string | null): AssistantLeadSummary {
    const match: TradeExample = AssistantDemoScenarioUtils.match(tradeLabel)
    return {
      name: EXAMPLE_NAME,
      contact: EXAMPLE_CONTACT,
      need: match.need,
      kind: match.kind,
      slots: match.slots,
      booked: false,
      hasPhoto: match.hasPhoto,
    }
  }

  /**
   * The alert SMS as the business receives it, worded like the real one (`AlertSms.new_request` on the API).
   * @param summary - What the visitor just sent.
   * @returns The text of the SMS.
   */
  static alertText(summary: AssistantLeadSummary): string {
    const need: string = (summary.need.trim() || 'rappel souhaité').replace(/[.!?…]+$/u, '')
    if (summary.booked && summary.slots) {
      return `RDV réservé le ${summary.slots} par ${summary.name}, ${summary.contact} : ${need}.`
    }
    const label: string =
      summary.kind === 'appointment'
        ? 'Nouvelle demande de RDV'
        : summary.kind === 'quote'
          ? 'Nouvelle demande de devis'
          : 'Nouvelle demande'
    const photo: string = summary.hasPhoto ? ' (photo)' : ''
    const slots: string = summary.slots ? `, pour ${summary.slots}` : ''
    return `${label}${photo} de ${summary.name}, ${summary.contact}${slots} : ${need}.`
  }

  /**
   * The example alert shown before any real request, for the trade.
   * @param tradeLabel - The Google Maps category, or null.
   * @returns The text of the example SMS.
   */
  static exampleAlertText(tradeLabel: string | null): string {
    return AssistantDemoScenarioUtils.alertText(AssistantDemoScenarioUtils.example(tradeLabel))
  }

  /**
   * The conversation the demo page plays by itself: the customer's opening, a reply, the customer again, a closing
   * reply that hands over. In French the opening and the replies follow the trade; the other languages share one
   * quote scenario. Nothing in it states a fact about the business.
   * @param lang - The widget's language.
   * @param tradeLabel - The Google Maps category, or null.
   * @param businessName - The business as the assistant names it.
   * @returns The turns, in order.
   */
  static script(lang: AssistantWidgetLang, tradeLabel: string | null, businessName: string): AssistantDemoScriptStep[] {
    const labels: AssistantExampleLabels = EXAMPLE_LABELS[lang]
    const match: TradeExample = AssistantDemoScenarioUtils.match(tradeLabel)
    const opening: string = lang === 'fr' ? match.opening : labels.visitor
    if (lang === 'fr' && match.kind === 'appointment') {
      const when: string = match.slots
        ? `${match.slots.charAt(0).toUpperCase()}${match.slots.slice(1)} si possible`
        : 'Le plus tôt possible'
      return [
        { role: 'user', content: opening },
        { role: 'assistant', content: 'Avec plaisir. Quel jour vous arrangerait ?' },
        { role: 'user', content: when },
        {
          role: 'assistant',
          content: `C'est noté. Je transmets à ${businessName}, qui vous confirme l'heure. Vous pouvez aussi réserver directement ci-dessous.`,
        },
      ]
    }
    if (lang === 'fr' && match.kind === 'question') {
      const firstName: string = EXAMPLE_NAME.split(' ')[0] ?? EXAMPLE_NAME
      return [
        { role: 'user', content: opening },
        {
          role: 'assistant',
          content: `Je comprends, je préviens ${businessName} tout de suite. À quel numéro peut-on vous rappeler ?`,
        },
        { role: 'user', content: `${EXAMPLE_CONTACT}, ${EXAMPLE_NAME}` },
        {
          role: 'assistant',
          content: `Merci ${firstName}, c'est transmis à ${businessName}. On vous rappelle au plus vite.`,
        },
      ]
    }
    return [
      { role: 'user', content: opening },
      { role: 'assistant', content: labels.askPhoto.replace('{business}', businessName) },
      { role: 'user', content: PHOTO_LABELS[lang].sent },
      { role: 'assistant', content: labels.thanks.replace('{business}', businessName) },
    ]
  }

  /**
   * The example of a trade, from its Google category.
   * @param tradeLabel - The Google Maps category, or null.
   * @returns The matching example, or the default one.
   */
  private static match(tradeLabel: string | null): TradeExample {
    const folded: string = AssistantDemoScenarioUtils.fold(tradeLabel ?? '')
    return (
      TRADE_EXAMPLES.find((example: TradeExample): boolean =>
        example.keywords.some((keyword: string): boolean => folded.includes(AssistantDemoScenarioUtils.fold(keyword))),
      ) ?? DEFAULT_EXAMPLE
    )
  }

  /**
   * Lower-case text without accents, to match keywords against a Google category.
   * @param value - The text.
   * @returns The folded text.
   */
  private static fold(value: string): string {
    return value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
  }
}
