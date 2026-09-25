import type { AssistantInstallGuide } from '~/types/AssistantInstallGuideCard'

/** Where to paste the widget's script on the platforms the clients use, in the order they come up. */
export const ASSISTANT_INSTALL_GUIDES: AssistantInstallGuide[] = [
  {
    key: 'wordpress',
    label: 'WordPress',
    steps: [
      "Dans l'administration, installez l'extension gratuite « WPCode » (Extensions → Ajouter).",
      'Ouvrez le menu Code Snippets → Header & Footer.',
      'Collez le script dans la zone « Footer », puis Enregistrer.',
      'Ouvrez le site en navigation privée : la bulle apparaît en bas à droite.',
    ],
    note: 'Un thème qui propose déjà une zone « Scripts de pied de page » (Astra, GeneratePress, Divi…) fait aussi l’affaire.',
  },
  {
    key: 'wix',
    label: 'Wix',
    steps: [
      'Tableau de bord Wix → Paramètres → Avancé → Code personnalisé.',
      '« + Ajouter du code », collez le script et nommez-le « Réceptionniste IA ».',
      'Ajouter le code à : Toutes les pages. Emplacement : Body, fin. Appliquer.',
      'Ouvrez le site en navigation privée : la bulle apparaît en bas à droite.',
    ],
    note: 'Le code personnalisé demande un forfait Wix payant avec un domaine connecté.',
  },
  {
    key: 'shopify',
    label: 'Shopify',
    steps: [
      'Boutique en ligne → Thèmes → bouton « … » du thème actif → Modifier le code.',
      'Ouvrez le fichier layout/theme.liquid.',
      'Collez le script juste avant la balise </body>, puis Enregistrer.',
      'Ouvrez la boutique en navigation privée : la bulle apparaît en bas à droite.',
    ],
    note: null,
  },
  {
    key: 'squarespace',
    label: 'Squarespace',
    steps: [
      'Paramètres → Avancé → Injection de code.',
      'Collez le script dans « Pied de page », puis Enregistrer.',
      'Ouvrez le site en navigation privée : la bulle apparaît en bas à droite.',
    ],
    note: 'Disponible à partir du forfait Business.',
  },
  {
    key: 'html',
    label: 'Sur mesure ou autre',
    steps: [
      'Ouvrez le gabarit commun à toutes les pages (pied de page, layout).',
      'Collez le script juste avant la balise </body>.',
      'Publiez, puis vérifiez en navigation privée.',
    ],
    note: 'Site fait par une agence ou un prestataire ? Envoyez-lui la ligne : une minute de travail.',
  },
]
