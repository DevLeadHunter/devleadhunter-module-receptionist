# Page d'une réceptionniste : le même atelier

## Pourquoi

Léo (07/10/2026) : « pour continuer la nouvelle version des pages configuration, tu peux me faire la maquette des autres modules ? … une vraie nouvelle version de la page configuration du module assistant IA, mais avant j'aimerais bien une maquette ». La page d'un site démo est devenue « l'atelier » (`docs/mockups/demo-site-page/`), retenue et en prod.

## Aujourd'hui (`captures-aujourdhui/`)

Captures du vrai logiciel en local, sur les deux vraies réceptionnistes de la prod (Dibodev, vendue, 18 conversations ; Tasty Korea Foodtruck, démo pas encore envoyée), iPad portrait 820 × 1180, clair et sombre, ordinateur.

- Sur iPad, la page d'une réceptionniste **vendue déborde à droite** (`ipad-1-01-resume-ecran.jpg`) : les valeurs du Résumé, l'onglet Configuration et les boutons d'actions sont hors écran.
- Le reste est une longue colonne de cartes : Résumé (12 lignes), lien, script, cinq boutons d'actions, vidéo, abonnement, puis quatre chiffres, demandes, questions sans réponse, guide d'installation, aperçu de la démo tout en bas.
- Sur ordinateur : colonne de contrôles à gauche, contenu à droite (le squelette que Léo a refusé pour le site).

## La maquette (`receptionniste-atelier-captures.html`, `captures-atelier/`, préfixes `dibodev-` et `tasty-`)

Construite dans le vrai logiciel sur la branche **`mockup/receptionist-page`** (worktree `dlh-mockup-site-page`), mêmes données réelles. Direction prise sans demander : **le même atelier que le site**, puisque Léo a dit « continuer la nouvelle version ». **Retenue le 07/10** (« vas-y continue ») avec une règle durable : **un outil n'ouvre un volet sous l'aperçu que s'il a besoin de voir la page ; sinon c'est une page dédiée** (comme « Plus »). Donc seule Identité a un volet ; Réponses, Demandes, Alertes, Vidéo et Plus sont des pages. Prompt pour l'autre modèle : `PROMPT-IMPLEMENTATION.md`.

- **La page de démo en plein écran** (`/ia/{slug}?internal=1`) dans un vrai téléphone ou un vrai écran d'ordinateur, réduit à l'échelle. Barre du haut : retour, portrait, nom, état (« En service chez le client », « En attente d'envoi », « Expire dans N j »), ligne « Léa · FR · EN · 6 conv. et 3 demandes sur 30 j · Bulle vue sur dibodev.fr », copier le lien, Ouvrir.
- **Six outils en bas** : Identité (volet : prénom, visage, ton, langues, couleur), puis des pages dédiées : Réponses (questions sans réponse avec compteur, réponses en place, sources), Demandes (dernières demandes avec compteur « à traiter », conversations), Alertes (email, mobile, SMS immédiat, heures calmes, email de résumé, Gmail bêta, modèle), Vidéo (la carte seule : l'encart « Comment elle part » a été retiré le 07/10, « pas utile », et doit l'être aussi sur la page du site), Plus.
- **La page change en direct** pendant qu'on tape : prénom, entreprise et couleur d'accent sont poussés dans la page de démo par `dlh:preview` (nouveau composable `useAssistantPreviewOverrides` dans demo-host, actif seulement en `_edit=1`). Capture `dibodev-ipad-07-identite-en-direct.jpg` : « Camille » et le vert apparaissent dans la page avant d'être publiés ; « Annuler » / « Publier » en haut, point ambre sur Identité.
- **Plus** = vraie page : quatre chiffres, lien de la démo (ou « Adresse de sa page » une fois vendue), script, guide d'installation, espace du client (envoyer, couper les liens), abonnement, informations, après la vente (régénérer, marquer vendu), supprimer.

## Code touché sur la branche

- `web/app/pages/dashboard/ai-assistants/[id].vue` : la page refaite (toute la logique de l'ancienne page conservée : régénérer, espace client, couper les liens, vendu, supprimer, vidéo, drawers).
- `web/app/composables/useAtelierToolSheet.ts` + `web/app/types/AtelierToolSheet.ts` (+ `UseAtelierToolSheetReturn` dans `types/Composables.ts`) : la mécanique du volet (ouverture, deux hauteurs, glissement, Échap, focus), **extraite** de la page du site. La page du site ne l'utilise pas encore : à migrer à l'implémentation pour ne pas garder deux copies.
- `web/app/components/atelier/DevicePreview.vue` + `web/app/types/AtelierDevicePreview.ts` : l'aperçu dans un vrai écran, générique (`pageUrl`, `previewMessage`), à faire adopter par la page du site à la place de `DemoSitesAtelierPreview`. Le dossier `components/atelier` n'est pas dans `nuxt.config.ts` : la page l'importe explicitement, à ajouter à la liste des dossiers.
- `AssistantSettingsForm.vue` : prop `section` (`identity` / `alerts` / `all`), `hasChanges`, `changedSections`, `save()`, `reset()` exposés, événement `draft` ; deux instances (identité dans le volet, alertes sur sa page), montées en `v-show` pour que les modifications survivent au changement d'outil ; « Publier » enregistre celles qui ont changé.
- `AssistantVideoCard.vue` (`isHeadingHidden`, `isFramed`), `AssistantSubscriptionCard.vue` (`isFramed`).
- `demo-host/app/pages/ia/[slug]/index.vue` + `composables/useAssistantPreviewOverrides.ts` : les surcharges en direct.

## À trancher

- Le volet Identité est long (six visages) : garder les visages dans le volet, ou les mettre dans une page comme « Plus ».
- « Réponses » et « Demandes » : des compteurs noirs sur l'outil ; le point ambre reste réservé aux modifications non publiées.
- Vérifier sur un vrai iPad (Safari) le glissement du volet.

## Comment rejouer les captures

Pile locale jetable (mémoire `local-dev-environment`) : `api-relay-8022` (son `.env` pointe `DEMO_HOST_BASE_URL` sur :3002), `demo-host-mockup-3002` (worktree), `web-mockup-5173` (worktree, branche `mockup/receptionist-page`) ; base seedée avec les deux vraies réceptionnistes (`scratchpad/real/seed_receptionists.py` de la session du 07/10, données lues en prod en lecture seule) ; `scratchpad/shoot_receptionist_today.py` (aujourd'hui) et `scratchpad/shoot_receptionist_atelier.py` (la maquette).

## État au 07/10/2026 : en ligne

L'atelier de la réceptionniste est sur `main` et en production (`da2f1e3d`, livré par l'autre session : web, demo-host et app Windows déployés). Elle a corrigé quatre défauts de la maquette en route (champs rendus deux fois, enregistrement des alertes qui renvoyait l'identité, « Annuler » qui laissait le prénom tapé dans l'aperçu, compteur des demandes recalculé sur six lignes), migré la page du site sur `useAtelierToolSheet` et `AtelierDevicePreview`, supprimé `AssistantSummaryCard`, `AssistantActionsCard`, `AssistantDemoPreviewCard` et `DemoSitesAtelierPreview`, et retiré l'encart « Comment elle part » des deux pages. Vérifié en local après coup sur la base seedée : Identité en direct, Annuler, pages dédiées, téléphone 390 px. Deux retouches faites ensuite : la carte vidéo du site limitée en largeur (la vignette prenait tout le volet et cachait les boutons) et les lignes de « Dernières demandes » qui passent la date et l'état à la ligne sur un téléphone. Pas encore vérifié : un vrai iPad (Safari, app installée).
