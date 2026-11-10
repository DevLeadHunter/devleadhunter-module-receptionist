import type { ModuleEmailVariable } from '~/utils/emailVariables'

/** The email variables the receptionist's offer adds (mirrors its API campaign offer), each after a core one. */
export const ASSISTANT_EMAIL_VARIABLES: ModuleEmailVariable[] = [
  {
    key: 'lien_assistant',
    token: '{lien_assistant}',
    label: 'Lien réceptionniste',
    description: 'Lien tracké vers la démo de la réceptionniste IA du prospect (vide sans réceptionniste).',
    example: 'https://demo.dibodev.fr/ia/le-gourmet',
    placeAfterKey: 'lien_demo',
  },
  {
    key: 'prenom_receptionniste',
    token: '{prenom_receptionniste}',
    label: 'Prénom de la réceptionniste',
    description: 'Prénom de la réceptionniste IA du prospect ; l’email n’est pas envoyé sans réceptionniste active.',
    example: 'Sofia',
    placeAfterKey: 'lien_assistant',
  },
  {
    key: 'receptionniste',
    token: '{receptionniste}',
    label: 'Réceptionniste (accordé)',
    description:
      '« une réceptionniste » ou « un réceptionniste », accordé au prénom de la réceptionniste IA (Léa, Nathan).',
    example: 'une réceptionniste',
    placeAfterKey: 'prenom_receptionniste',
  },
  {
    key: 'assistant_virtuel',
    token: '{assistant_virtuel}',
    label: 'Assistant virtuel (accordé)',
    description:
      '« une assistante virtuelle » ou « un assistant virtuel », accordé au prénom de la réceptionniste IA (Léa, Nathan).',
    example: 'une assistante virtuelle',
    placeAfterKey: 'receptionniste',
  },
  {
    key: 'lien_video_assistant',
    token: '{lien_video_assistant}',
    label: 'Lien vidéo réceptionniste',
    description: 'URL de la page vidéo de la réceptionniste IA (vide sans vidéo générée).',
    example: 'https://demo.dibodev.fr/va/le-gourmet',
    placeAfterKey: 'vignette_video',
  },
  {
    key: 'vignette_video_assistant',
    token: '{vignette_video_assistant}',
    label: 'Vignette vidéo réceptionniste',
    description: 'Bloc image cliquable de la vidéo de la réceptionniste IA (HTML prêt à coller, renvoie au player).',
    example: '[vignette cliquable de la vidéo de la réceptionniste]',
    placeAfterKey: 'lien_video_assistant',
  },
  {
    key: 'prix_assistant',
    token: '{prix_assistant}',
    label: 'Prix réceptionniste',
    description:
      'Prix mensuel de la réceptionniste IA configuré, dans la monnaie du prospect : « 79 € », « ≈ 70 CHF ».',
    example: '79 €',
    placeAfterKey: 'prix',
  },
]
