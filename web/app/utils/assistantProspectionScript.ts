import type { ProspectionScriptSegment } from '~/composables/useProspectionScript'

/**
 * Default receptionist script: « votre réceptionniste », never a name or a pronoun, middle take in the video's order.
 * @param presenterName - The connected user's full name, woven into the greeting.
 * @param companyName - The user's optional business name, appended to the greeting when set.
 * @returns The three default takes.
 */
export function buildAssistantScript(presenterName: string, companyName: string): ProspectionScriptSegment[] {
  const name: string = presenterName.trim()
  const company: string = companyName.trim()
  const presenter: string = company ? `${name} de ${company}` : name
  return [
    {
      id: 'intro',
      title: 'Intro',
      staging: 'Vous, en plein écran. Le prénom du prospect s’affiche à côté de vous.',
      targetSeconds: 6,
      text: name
        ? `Bonjour, moi c'est ${presenter}. Je vous ai préparé votre réceptionniste, rien que pour votre entreprise.`
        : 'Bonjour. Je vous ai préparé votre réceptionniste, rien que pour votre entreprise.',
    },
    {
      id: 'middle',
      title: 'La réceptionniste répond, puis l’espace du patron',
      staging:
        'Le chat joue un exemple pendant l’essentiel de la prise : un client écrit, une photo est demandée, la ' +
        'demande est transmise, puis les créneaux de rendez-vous s’ouvrent. Les sept dernières secondes montrent ' +
        'l’espace où arrivent les demandes. Vous passez en petite pastille ronde, en bas à droite.',
      targetSeconds: 30,
      text:
        'Votre réceptionniste est en ligne sur votre site, ou depuis votre fiche Google, vingt-quatre heures sur ' +
        'vingt-quatre. ' +
        "Un client pose une question : réponse immédiate, avec vos horaires et vos prestations, jamais rien d'inventé. " +
        'Il envoie une photo pour un devis : sa demande est notée, photo comprise. ' +
        "Il veut un rendez-vous : c'est réservé dans votre agenda. " +
        "Et ça, c'est votre espace : chaque demande arrive ici, et vous recevez un SMS.",
    },
    {
      id: 'outro',
      title: 'Outro',
      staging: 'Retour sur vous en plein écran, pour l’appel à l’action.',
      targetSeconds: 12,
      text:
        "Le lien pour l'essayer est juste sous la vidéo. " +
        'Posez-lui une question, envoyez-lui une photo, et dites-moi ce que vous en pensez. Bonne journée !',
    },
  ]
}
