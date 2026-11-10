# Maquettes de la réceptionniste

Les maquettes HTML du module, gardées dans le dépôt pour qu'aucune ne se perde dans un fil de discussion. Chacune s'ouvre par un double-clic dans un navigateur : aucun serveur, aucune installation.

Elles viennent du dépôt principal (`DevLeadHunter/devleadhunter`, `docs/mockups/`), qui garde leur ligne dans son index avec un lien ici. Les maquettes du reste du produit (sites démo, recherche de prospects, mails…) sont restées là-bas.

## En attente de décision

### Présence humaine sur la démo (`human-presence/`)

La note qui couvre les trois briques (carte « Qui est derrière ce site », réceptionniste dans le bandeau, mail franc) est restée dans le dépôt principal : `docs/mockups/human-presence/NOTE.md`, partie 2 pour la réceptionniste.

| Fichier | Ce qu'il montre | État |
|---|---|---|
| `human-presence/banner-receptionist.html` | La réceptionniste Léa dans le bandeau : onglet dans la carte (position 1) ou panneau séparé (position 2) | En attente |

## Faites

### Page d'une réceptionniste (`receptionist-page/`)

| Fichier | Ce qu'il montre | État |
|---|---|---|
| `receptionist-page/receptionniste-atelier-captures.html` (+ `captures-atelier/`) | **Le même atelier que pour un site démo** : la page de démo en plein écran dans un vrai téléphone, six outils en bas ; Identité en volet (la page change en direct pendant qu'on tape), Réponses, Demandes, Alertes, Vidéo et Plus en pages dédiées ; captures du vrai logiciel sur les deux vraies réceptionnistes, iPad portrait, sombre, ordinateur | **Retenue le 07/10, codée et en prod le jour même** (`da2f1e3d`) ; règle : pas de volet quand l'aperçu n'est pas utile ; voir la note pour ce qui reste à vérifier sur un vrai iPad |
| `receptionist-page/captures-aujourdhui/` | L'état d'avant l'atelier sur iPad : la page d'une réceptionniste vendue déborde à droite, le reste est une longue colonne de cartes | Constat |
| `receptionist-page/NOTE.md` | Le pourquoi, le constat, ce que l'atelier contient, le code touché, les points à trancher | À jour |
| `receptionist-page/PROMPT-IMPLEMENTATION.md` | Le prompt à coller à un modèle de code pour implémenter l'atelier de la réceptionniste à partir de la branche de maquette | À jour |
