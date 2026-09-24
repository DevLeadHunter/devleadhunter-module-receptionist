# Réceptionniste IA — argumentaire

Une page pour tenir 79 à 99 € par mois face à « IONOS le fait à 15 € ».

## La promesse

**Plus aucune demande sans réponse.**

Trois preuves, à montrer dans la démo :

1. **Elle répond 24 h/24, dans la langue du client** : français, néerlandais, allemand, anglais, luxembourgeois. Le
   visiteur de 22 h ou du dimanche a sa réponse, et la demande arrive au commerce.
2. **Devis par photo** : le visiteur envoie la photo de sa fuite, de sa rayure ou de sa toiture. La demande arrive
   décrite et classée (devis, ou urgence si la photo montre un risque).
3. **Rendez-vous pris** : directement dans l'agenda Google du commerce, avec une confirmation par SMS ou par email
   et un rappel la veille. Sans agenda connecté, le visiteur choisit une ou deux demi-journées et le commerce
   confirme.

Un chiffre : **la part des demandes reçues hors horaires**. Chaque assistant la mesure (dashboard, rapport mensuel).
À citer dès que les premières démos l'ont mesurée : « X % des demandes arrivent quand vous êtes fermé ». En
attendant, la page de démo montre une estimation calculée sur les horaires du commerce (« ≈ 18 demandes » que
l'assistante aurait prises quand c'est fermé), présentée comme telle, avec son calcul.

## Face à IONOS à 15 €

| | IONOS (et autres chatbots) | Réceptionniste IA |
|---|---|---|
| Mise en place | Vous l'installez, vous la nourrissez | Déjà en place avant le premier contact : la démo est construite sur votre fiche Google et votre site |
| Ce qu'elle fait d'un échange | Une conversation | Une demande classée (devis, rendez-vous, urgence) et résumée |
| Quand une demande arrive | Vous allez voir | SMS pour ce qui ne peut pas attendre, email pour le reste, rappel le lendemain si rien n'est traité |
| Photos, rendez-vous | Non | Devis par photo, rendez-vous dans votre agenda |
| Suivi | Non | Un espace client (demandes, réglages, abonnement) et un rapport chaque mois |

Le prix ne se compare pas à un logiciel : il se compare à **une demi-journée de secrétariat par mois**. Une seule
demande de devis rattrapée le paie.

## Objections

**« J'ai déjà un formulaire. »**
Un formulaire attend qu'on le remplisse. Elle répond aux questions, rassure, et ne laisse partir personne sans ses
coordonnées. Les demandes arrivent triées et résumées, pas en vrac.

**« Je réponds moi-même. »**
Le soir, le week-end, sur un chantier ? Elle prend la demande et vous prévient par SMS ; vous rappelez quand vous
pouvez. Elle ne remplace pas votre réponse, elle évite qu'une demande attende.

**« Mes clients appellent. »**
Ceux qui appellent continuent d'appeler. Elle capte les autres : ceux qui écrivent plutôt que d'appeler, ceux qui
cherchent le soir, ceux qui parlent une autre langue.

**« Et si elle dit une bêtise ? »**
Elle répond uniquement à partir de votre fiche, de votre site et de vos documents. Jamais de prix, de délai ni
d'engagement qui n'y figure pas : elle propose de noter la demande pour que vous rappeliez. Quand une page de votre
site répond à la question, elle en donne le lien. Chaque conversation est journalisée.

**« Et mes données ? »**
Les réponses passent d'abord par Mistral, une entreprise française. Un secours hors d'Europe prend le relais en
cas de panne, sauf si l'assistant est réglé sur « modèle européen uniquement ». Les photos envoyées sont supprimées
au bout de 90 jours.

**« Encore un abonnement. »**
Premier mois satisfait ou remboursé, sans engagement : la résiliation se fait depuis l'espace client.
L'installation est incluse (un script à coller sur le site, ou on le fait).

## Nom du module et de la persona (à trancher)

- **« Réceptionniste IA »** dit le métier (accueillir, prendre les demandes, prévenir) et non la technologie. C'est le
  nom des textes de vente et de la page `/ia`. Recommandé pour la vente.
- **« Assistante IA »** est plus vague et se confond avec les chatbots.
- **Prénom** : féminin par défaut (« Sofia »). Un prénom masculin est reconnu et les textes s'accordent. Un prénom
  neutre reste possible.

Le nom du module dans le sélecteur du dashboard n'a pas changé.

## Ancrages prix par pays

| Pays | Prix conseillé |
|---|---|
| France | 79 €/mois (790 €/an) |
| Belgique, Luxembourg | 89 à 99 €/mois |
| Suisse | 99 CHF/mois |

Le prix par défaut du compte est 79 € (Paramètres → Facturation & paiement) ; l'ancrage BE/LU/CH est une recommandation.
Le paiement Stripe est en euros : un prix en CHF n'existe pas encore.

## Avant de s'en servir

- « Mistral d'abord » suppose la clé Mistral en place ; sans elle, les réponses passent par Groq.
- « Résiliation depuis l'espace client » suppose le portail Stripe configuré (Settings → Billing → Customer portal).
- Le chiffre « X % des demandes hors horaires » attend les premières mesures.
