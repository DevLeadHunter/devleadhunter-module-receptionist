# Module Assistant IA — DevLeadHunter

> Comment est généré, servi, personnalisé et vendu l'**assistant IA** — le réceptionniste
> conversationnel généré par prospect, multilingue, à la marque du prospect. Ce document est la
> **source de vérité** du module (le 2ᵉ produit vendable, à côté du module Sites web).

## TL;DR

- **1 assistant = 1 prospect.** Généré depuis les mêmes données que la démo de site (enrichissement),
  servi publiquement par `slug`, il répond aux visiteurs **strictement** sur la base de sa fiche de
  connaissance (`knowledge_json`) — jamais d'invention. Trois sources : l'enrichissement Google Maps,
  le **site web du prospect** (crawl léger à la génération et à la régénération,
  `services/ai_assistant/website_crawler.py` : accueil + ≤ 7 pages internes « offre » d'abord —
  prestations, tarifs, FAQ, contact… —, texte sans nav/footer, 4 000 caractères par page et 24 000 au
  total, ignoré si le site est `dead`/`placeholder`) et le **`content_json` du site généré** pour lui
  (à propos, cartes de prestations, FAQ). Le prompt encadre ces extraits comme des **données** (jamais
  des instructions) et demande de dire « selon votre site » quand la réponse en vient.
- **Multilingue par pays.** FR / NL / DE / EN / LU. Le widget s'ouvre dans la langue du visiteur ;
  le chat détecte et répond **dans sa langue**, sans jamais mélanger.
- **À la marque du prospect** : nom d'assistant, ton, couleur d'accent tirée du logo. Tout est
  personnalisable et **régénérable** sans changer le lien public ni la marque.
- **Se vend par campagne** : la variable `{lien_assistant}` existe en email (ancre tracée) et en SMS
  (lien nu), en miroir de `{lien_demo}`. Une **vidéo de prospection** optionnelle (générée sur le PC
  comme le site, fallback VPS) se joue sur `/va/{slug}`.
- **Cible** : commerces avec site (BE / LU / CH / FR) — vente par **abonnement** (increment C3, voir
  plus bas, **en attente de la décision prix**).

## Architecture

Le module **calque le moteur des sites de démo**, en plus simple : pas de Storyblok, l'assistant se
rend depuis son `knowledge_json`.

```
Prospect ──enrichissement──▶ build_fields ──▶ AiAssistant (slug, knowledge_json, persona)
                                   │                     │
              config_builder ◀─────┘                     ├─ /a/{slug}       page de démo (vente)
              knowledge_builder ◀──┘                     ├─ /embed/{slug}   widget en iframe
                                                         └─ /public/{slug}/chat  réponse groundée
```

### Génération (`services/ai_assistant/assistant_service.py`)

`create_for_prospect(db, user_id, prospect)` :

1. `enrichment_service.ensure_enriched(...)` — réutilise l'enrichissement existant, l'exécute une fois sinon.
2. `build_fields(...)` assemble les colonnes persistables (pur, sans DB) via :
   - **`config_builder`** — accent de marque (extrait du logo, sauf `use_brand_color=False`), langues
     par pays (`LU: fr/de/en/lu`, `BE: fr/nl/en`, `CH: fr/de/en`, `FR: fr/en`), persona par défaut
     (`Sofia`, ton « chaleureux, professionnel et concis »).
   - **`knowledge_builder`** — la fiche de connaissance (identité, faits, horaires, services…) tirée
     du prospect + enrichissement, avec la consigne de **répondre dans une seule langue** à la fois.
3. Le `slug` est dérivé du nom (unique, suffixé `-2`, `-3`… en cas de collision), et l'accent est
   rangé dans `knowledge_json['palette']['accent']` pour être servi en une lecture.

### Régénération

`regenerate_for_prospect(db, assistant, prospect)` reconstruit la **connaissance** et les
**coordonnées** depuis les dernières données du prospect (ou depuis un moteur de KB amélioré), en
**préservant** la marque et la persona : nom affiché, nom d'assistant, ton, langues, accent et
**slug** sont conservés — un lien déjà envoyé continue de fonctionner à l'identique.

### Personnalisation

`update(db, assistant, fields)` applique une édition partielle (seules les clés fournies sont
touchées) : `assistant_name`, `business_name`, `languages`, `tone`, `use_brand_color`, et
`accent_color` (réécrit dans `knowledge_json['palette']`, chaîne vide = accent neutre).

### Réponse groundée (`services/ai_assistant/chat_service.py`)

`answer(...)` : prompt système qui **interdit d'inventer**, réponse dans la langue du visiteur,
historique borné (`MAX_HISTORY_MESSAGES = 12`, `MAX_MESSAGE_CHARS = 2000`). Si le modèle est
indisponible, un **fallback sûr** garde la conversation vivante (invite à laisser ses coordonnées)
plutôt que d'échouer. Modèle via `llm_service` (Groq).

Le prompt (`knowledge_builder.render_system_prompt`) porte aussi la **date et l'heure locales** de
l'entreprise (heure de Paris, commune aux pays ciblés) pour répondre à « ouvert aujourd'hui ? » depuis
les horaires, interdit de laisser entendre qu'un **service absent de la fiche** existe (livraison,
réservation, devis…), et accorde son vocabulaire au **genre de la persona**, déduit du prénom
(`config_builder.resolve_persona_gender`, liste `masculine_first_names.py`, féminin par défaut). Ce genre
est exposé dans la config publique (`assistant_gender`) pour les textes du widget et des pages démo.

## Endpoints (`api/api/v1/routes/ai_assistants.py`)

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/ai-assistants` | Générer un assistant pour un prospect |
| `GET` | `/ai-assistants` | Lister ses assistants (filtre `?prospect_id=`) |
| `GET` | `/ai-assistants/leads` | Anciens contacts captés (lecture seule, historique) |
| `GET` | `/ai-assistants/requests` | Lister les demandes (`?assistant_id=`, `?status=`) + `pending_count` |
| `PATCH` | `/ai-assistants/requests/{id}` | Changer le statut (`new` / `handled` / `dropped`) ou la note d'une demande |
| `PATCH` | `/ai-assistants/{id}` | Personnaliser (nom, persona, langues, accent, alertes au commerçant, EU only) |
| `POST` | `/ai-assistants/{id}/regenerate` | Régénérer la connaissance (garde marque + slug) |
| `POST` | `/ai-assistants/{id}/video` | Générer la vidéo de prospection (fond serveur / VPS) |
| `GET` | `/ai-assistants/{id}/video-context` | Contexte pour le build desktop (sidecar) |
| `POST` | `/ai-assistants/{id}/video-final` | Recevoir la vidéo montée sur le PC → R2 |
| `DELETE` | `/ai-assistants/{id}/video` | Supprimer la vidéo générée |
| `DELETE` | `/ai-assistants/{id}` | Supprimer (soft-delete) |
| `GET` | `/ai-assistants/public/{slug}` | Config publique du widget (+ vidéo si prête) |
| `POST` | `/ai-assistants/public/{slug}/chat` | Réponse groundée à un message |
| `GET` | `/ai-assistants/public/{slug}/appointment-slots` | Demi-journées ouvertes proposées pour un rendez-vous (`days`, `max_chosen`) |
| `POST` | `/ai-assistants/public/{slug}/lead` | Capturer une demande (coordonnées + `session_id` + `internal` + `slots` : 2 demi-journées au plus ; 422 si l'une n'est plus proposée) |
| `POST` | `/ai-assistants/public/{slug}/photo` | Photo pour un devis (multipart : `file`, `session_id`, `language`, `internal`) |
| `GET` | `/ai-assistants/public/requests/{id}/handled` | Lien signé de l'email de résumé : page de confirmation (ne change rien) |
| `POST` | `/ai-assistants/public/requests/{id}/handled` | Même lien signé : marque la demande traitée (bouton de la page) |
| `POST` | `/ai-assistants/public/{slug}/interest` | Signaler l'intérêt de l'owner (pop-up « me contacter ») |
| `POST` | `/ai-assistants/{id}/client-link` | Lien de l'espace client d'un assistant vendu (`send` : l'envoyer par email au commerçant) |
| `GET` | `/ai-assistants/client/{token}` | Espace client : demandes, rapport, réglages, abonnement |
| `POST` | `/ai-assistants/client/{token}/requests/{id}/handled` | Marquer traitée une demande depuis l'espace client |
| `PATCH` | `/ai-assistants/client/{token}/settings` | Prénom, langues, mobile d'alerte, SMS / email oui-non |
| `POST` | `/ai-assistants/client/{token}/billing-portal` | Session du portail Stripe Billing (retour sur l'espace) |
| `POST` | `/ai-assistants/client/{token}/renew` | Depuis un lien expiré : nouveau lien envoyé à l'adresse du commerçant |

Les endpoints publics du widget sont **rate-limités par IP** (`services/rate_limiter.py`) : chat
30 / 300 s, créneaux 30 / 300 s (compteur à part), lead 8 / 300 s, photo 6 / 600 s (fenêtre glissante en
mémoire). Le lien « traitée » n'a pas de limite : sans
signature valide et non expirée, il ne fait rien. L'espace client : 120 appels / 300 s par IP (la page se charge
dans le navigateur du visiteur, jamais depuis le serveur du demo-host), et 3 nouveaux liens par heure et 6 par jour
et par assistant. Ses routes publiques vivent dans `api/api/v1/routes/ai_assistant_client_space.py`.

## Le widget (`demo-host/app/components/AssistantChat.vue`)

C'est le **produit** que le client colle sur son site. Il porte :

- **5 langues d'interface** (FR / NL / DE / EN / LU) : accueil, suggestions, placeholder, libellés du
  formulaire de rappel, réponse de secours — un jeu complet par langue.
- **Ouverture dans la langue du visiteur** : au montage, la langue du navigateur est choisie si
  l'assistant l'offre (sinon FR). Le visiteur peut changer ; le chat répond toujours dans **sa** langue.
- **Persistance de conversation** : la conversation (et la langue) est gardée en `localStorage`
  (`dlh-assistant-<slug>`, bornée à 40 messages) — un visiteur qui recharge ou change de page **retrouve
  son fil**. Écriture/lecture en `try/catch` (mode privé) : le widget marche sans.
- **Capture de demande** : nom + contact + besoin + langue, avec l'identifiant de session du widget
  (la demande est liée à la conversation) et `internal: true` sur une visite `?internal=1`.
- **Photo pour un devis** : bouton appareil photo dans la barre de saisie et chip « 📷 Envoyer une photo
  pour un devis » (avant le premier échange). Un panneau affiche d'abord la mention RGPD (photo utilisée
  pour le devis, supprimée après 90 jours, pas de personnes) puis ouvre le sélecteur (appareil photo ou
  galerie). La photo est réduite en JPEG côté navigateur (`utils/PhotoCompressionUtils.ts`, 1600 px,
  8 Mo max ; un HEIC que le navigateur ne sait pas lire part tel quel), montrée en vignette, jamais mise
  dans la conversation stockée ni envoyée au chat (seule la ligne « 📷 Photo envoyée » l'est). La réponse
  de l'assistante s'affiche, puis le formulaire de coordonnées s'ouvre avec le besoin pré-rempli.
  3 photos par visite ; event PostHog `assistant_photo_sent`.
- **Demande de rendez-vous** (sans agenda connecté) : chip « 📅 Prendre rendez-vous » (avant le premier
  échange) et bouton calendrier dans la barre de saisie. Le panneau charge les demi-journées ouvertes
  (`GET /public/{slug}/appointment-slots`) et le visiteur en coche 1 ou 2 (matin / après-midi, pas de saisie
  libre ; une troisième remplace la plus ancienne), puis laisse ses coordonnées. La demande part avec
  `slots` et devient une demande de rendez-vous ; la confirmation au visiteur reprend ses créneaux et dit
  que le commerce confirmera l'un des deux. Si un créneau n'est plus proposé à l'envoi (passage de minuit),
  le widget le dit et recharge les créneaux. Dates dans la langue du widget (`Intl.DateTimeFormat`).
  Pendant le choix des créneaux et le formulaire, les suggestions et « Être rappelé » s'effacent : le
  panneau tient dans l'iframe de 440 × 680 (la liste des jours défile, les boutons restent visibles).
- **Embarqué** : quand il tourne en iframe, il envoie `postMessage` pour se redimensionner entre la
  bulle fermée et le panneau ouvert.

### Page de démo `/a/{slug}` (`demo-host/app/pages/a/[slug].vue`)

Surface de **vente** : DA éditoriale crème/encre/Fraunces, à l'**accent du prospect**, indicateur
« En ligne », trois arguments (24h/24, langue du visiteur, capture des contacts) et le widget en vedette.

### Embed loader (`demo-host/public/ai-assistant.js`)

Une seule ligne chez le client :

```html
<script src="https://demo.dibodev.fr/ai-assistant.js" data-slug="son-slug" defer></script>
```

Le script monte un iframe transparent (bas-droite) vers `/embed/{slug}?embed=1` (+ `internal=1`
repris de la page hôte), ne touche à aucun style de la page hôte, sans dépendance. Dialogue par
`postMessage` : le widget annonce `dlh-assistant-ready`, le loader répond `dlh-assistant-host`
(largeur du viewport hôte, rejouée au resize) qui pilote le rendu mobile (`.ai-panel--mobile`,
bulle masquée) — la media query de l'iframe ne dit rien de l'écran du client ; le widget envoie
`dlh-assistant-resize` avec l'empreinte exacte du lanceur (fermé) ou `open: true` (440×680, plein
écran sur mobile), donc aucune zone morte au-dessus du site hôte ; `dlh-assistant-unavailable`
(slug inconnu, démo expirée) fait retirer l'iframe. Page hôte de test : `/embed-test.html?slug=…`.

### Journal des conversations (`services/ai_assistant/conversation_service.py`)

Chaque tour de chat public est journalisé côté serveur : `ai_assistant_conversations` (une ligne par
`session_id` généré et conservé par le widget, avec langue, `started_at`, `last_message_at`,
`message_count`) + `ai_assistant_messages` (rôle, contenu borné à 2 000 caractères). Le journal ne
bloque jamais la réponse (échec = warning). L'owner lit les 20 dernières conversations d'un assistant
(`GET /ai-assistants/{id}/conversations`, drawer « Ce que vos visiteurs ont demandé » de la page
Assistants IA) et voit `conversations_7d` / `conversations_30d` dans la liste (conversations dont le
dernier message tombe dans la fenêtre : un visiteur qui revient compte à nouveau) ; purge après 90 jours
sans message par la boucle de nettoyage. C'est la seule visibilité une fois le widget vendu (sur le
site du client, hors PostHog). Une visite `?internal=1` (le widget envoie `internal` avec chaque message)
est journalisée avec `is_test` : visible dans le journal, hors des compteurs, du rapport mensuel et du
drapeau churn.

Tracking PostHog : `useDemoTracking.init` accepte l'iframe pour la surface `assistant` (la page embed la
passe), donc `assistant_opened` / `assistant_message_sent` / `assistant_lead_submitted` partent aussi
depuis un site client tant que la démo est `active` ; un assistant vendu n'est plus tracé (journal
serveur seulement).

## Demandes (`services/ai_assistant/request_service.py`)

Un visiteur qui laisse ses coordonnées devient une **demande** (`ai_assistant_requests`), l'unité que
le commerçant traite. Elle remplace `ai_assistant_leads` pour toute nouvelle capture ; les anciens
leads y ont été recopiés une fois (`legacy_lead_id`, statut `handled`) et leur table reste en lecture.

- **Une demande par session** : la même `session_id` met à jour sa demande tant qu'elle est `new` et
  a moins de 24 h (coordonnées, besoin) au lieu d'en créer une deuxième. Une demande déjà traitée, sans
  suite ou plus ancienne n'est jamais rouverte : le visiteur qui revient ouvre une nouvelle demande.
  Sans session, chaque envoi crée une demande.
- **Liée au journal** : `conversation_id` pointe la conversation de la session ; sa transcription
  alimente le résumé et l'email.
- **Typée et résumée** en arrière-plan (`request_analyzer.py`, `llm_service.complete_json`) :
  `type` ∈ `question | quote | appointment | urgent | other` et `need_summary` (1-2 phrases factuelles en
  français, jamais de prix). Sans modèle ou réponse hors contrat : mots-clés FR/NL/DE/EN pour le type,
  mots du visiteur pour le résumé. Le visiteur reçoit sa confirmation sans attendre.
- **Hors horaires** : `received_outside_hours` est calculé à la capture depuis
  `knowledge_json['opening_hours']` à l'heure de Paris (`opening_hours.py` ; plages après minuit,
  « Fermé », « 24h/24 ») ; horaires absents ou illisibles = `NULL` (inconnu), jamais « hors horaires ».
- **Annoncée une fois** : `owner_notified_at` est réservé par un `UPDATE … WHERE owner_notified_at IS
  NULL` avant tout envoi (deux passes concurrentes n'annoncent pas deux fois). L'annonce part en tâche de
  fond juste après la capture ; `request_runner.py` (boucle de 5 min lancée au démarrage de l'API)
  reprend celles qu'un redémarrage a perdues (demandes de plus de 2 min et de moins de 24 h). Annonce :
  push à l'owner (type, hors horaires) et, **si l'assistant est vendu** (`delivered`), les alertes au
  commerçant (section suivante) : email de résumé au commerce (`AiAssistant.email`, sinon l'email du
  prospect, sinon celui du client saisi au paiement Stripe de l'abonnement en cours) via l'identité
  d'envoi de l'owner en mode transactionnel (`send_via_user_identity`, sans
  `prospect_id` : le prospect n'est pas marqué contacté) et SMS. Une démo n'écrit jamais au prospect.
  L'email montre le besoin, les coordonnées cliquables (tel / mailto), la conversation, le lien de
  l'espace client et un bouton « Marquer comme traitée » : lien signé HMAC (`SECRET_KEY`) valable
  30 jours (`request_links.py`). Le
  `GET` du lien n'affiche qu'une page de confirmation (les antivirus de messagerie ouvrent les liens) ;
  c'est son bouton (`POST` sur la même URL) qui marque la demande traitée.
- **Créneaux souhaités** (`services/ai_assistant/appointment_slots.py`, colonne
  `appointment_slots_json` : `[{"date": "2026-09-28", "period": "morning"}]`) : sans agenda connecté,
  l'assistant ne réserve rien. Il propose les 6 prochains jours ouverts à partir de demain (sur 21 jours),
  chacun avec ses demi-journées ouvertes d'après `knowledge_json['opening_hours']` : le matin est ouvert si
  le commerce l'est à 8 h 30, 9 h 30, 10 h 30 ou 11 h 30, l'après-midi à 13 h 30, 14 h 30, 15 h 30, 16 h 30 ou
  17 h 30 (heure de Paris). Jour sans horaire lisible : du lundi au vendredi. À la capture, les demi-journées
  choisies (2 au plus, dédoublonnées, triées) doivent être encore proposées, sinon 422 et rien n'est
  enregistré. Une demande avec créneaux est typée `appointment` dès la capture, sauf urgence (lue par
  l'analyse, ou sur une photo). L'email de résumé ajoute un bloc « Créneaux souhaités (à confirmer) »
  (« mar. 22/09, après-midi ») ; le SMS les porte juste après le contact, jamais coupés (« …, 06 11 22 33 44,
  pour mar. 22/09 après-midi ou ven. 25/09 matin : Fuite… ») : si la place manque, le nom est raccourci, puis
  seul le premier créneau reste (l'email les a tous). Le dashboard et l'espace client les affichent sous le
  résumé.
- **Visite interne** (`internal: true`) : la demande est enregistrée avec `is_test`, typée, jamais
  annoncée, exclue des compteurs et de l'onglet « À traiter » (visible sous « Toutes », badge Test).
- **Statuts** : `new` → `handled` (ou `dropped`), `handled_at` suit ; note libre de l'owner.

La liste des assistants porte `requests_7d`, `requests_30d` et `requests_outside_hours_pct` (part des
demandes des 30 derniers jours reçues hors horaires, parmi celles dont les horaires sont connus).

## Modèles IA : Mistral d'abord, Groq en secours (`services/ai_assistant/llm_router.py`)

Les appels qui touchent aux visiteurs passent par `assistant_llm_router` : le **chat** du widget
(`AssistantLlmUsage.CHAT`), les **photos de devis** (`VISION`) et l'**analyse des demandes** (`REQUEST`).
Le reste du produit (génération de la fiche, emails, relances…) reste sur Groq (`llm_service`).

- **Mistral** (`services/mistral_service.py`, La Plateforme, API compatible OpenAI) : `MISTRAL_API_KEY`,
  `MISTRAL_CHAT_MODEL` et `MISTRAL_VISION_MODEL` (défaut `mistral-small-latest`, qui lit aussi les images).
  Avec un secours possible, Mistral a la moitié du temps de l'appelant et un seul essai ; un appel « EU
  only » a tout le temps et une relance rapide (429 / 5xx, `retry-after` plafonné à 3 s). Une requête que
  Mistral refuse comme mal formée (400 / 422) n'est pas une panne : pas d'alerte, le secours répond.
- **Secours Groq** : Mistral en panne → l'appel part chez Groq (modèle par défaut, ou le modèle vision
  vérifié pour les photos ; aucun modèle vision → pas de réponse), avec un avertissement dans le log et une
  notification aux admins envoyée en tâche de fond (une au plus par usage et par type de panne toutes les
  30 min : bascule sur Groq, Groq aussi en panne, EU only sans réponse, EU only sans clé). Jamais l'inverse.
  Sans `MISTRAL_API_KEY`, tout reste sur Groq, sans alerte.
- **« EU only »** (`ai_assistants.eu_only`, NULL = non, interrupteur dans « Personnaliser », refusé en 422
  tant que `MISTRAL_API_KEY` n'est pas configurée) : l'assistant ne part **jamais** chez Groq ; en panne,
  l'appel rend « pas de réponse » et chaque appelant garde sa réponse sûre (chat : proposer de laisser ses
  coordonnées ; photo : réponse neutre ; analyse : mots-clés).
- **Chat** : seule une conversation qui se termine par un message du visiteur part au modèle ; sinon la
  réponse sûre, sans appel.
- **Journal** : chaque appel servi écrit une ligne `assistant_llm_call` (usage, fournisseur, modèle,
  latence totale en ms — tentative Mistral ratée comprise —, tokens, coût estimé en €, secours oui/non, EU
  only), en INFO : `main._configure_logging` garde ce logger au niveau INFO en production. Prix par million
  de tokens réglables (`MISTRAL_EUR_PER_MTOK_IN/OUT`, `GROQ_EUR_PER_MTOK_IN/OUT`, prix du modèle de chat :
  une photo lue par un autre modèle est une estimation).
- **Bench** : `python scripts/bench_assistant_llm.py [slugs…]` pose 20 questions (FR / DE / NL / EN) à
  3 assistants sur chaque fournisseur configuré : latence moyenne et p95, tokens, coût par réponse et
  par conversation (4 réponses), réponses citant un prix ; les réponses vont dans un fichier Markdown.
- **Argument « données en Europe »** : ne l'afficher (page `/ia`, emails) qu'une fois vérifiées les
  conditions de Mistral (région d'hébergement, rétention, non-entraînement sur les données API, DPA).

## Devis par photo (`services/ai_assistant/photo_service.py`)

- **Réception** (`POST /public/{slug}/photo`) : le formulaire est lu à la main, **après** la limite de
  débit et le contrôle du `Content-Length` (absent : 411 ; au-delà de 8 Mo + enveloppe : 413), pour
  qu'aucun corps démesuré ne soit écrit sur disque. Image illisible ou corrompue : 415 (HEIC compris :
  pas de décodeur HEIC côté serveur) ; plus de 50 mégapixels déclarés : 413 avant tout décodage ; session
  vide : 400 ; stockage indisponible : 503. Quota : 3 photos par demande (409) — photos gardées de la
  session sur 24 h, hors celles d'une demande déjà traitée. La photo est ré-encodée hors de la boucle
  d'événements en JPEG 1600 px (orientation corrigée, **aucune métadonnée** : EXIF, position GPS,
  commentaire) puis stockée sur R2 sous `images/assistant-photos/{yyyy}/{mm}/{uuid}.jpg` (clé non
  devinable, URL publique). La ligne `ai_assistant_photos` est écrite avant l'envoi à R2 (une coupure en
  cours de route laisse une clé connue de la purge) et la connexion à la base est rendue pendant les
  appels lents (stockage, vision).
- **Vision** (`AiAssistantPhotoVision`, modèle vision de `llm_service`) : JSON `relevant`, `object`,
  `damage`, `urgency` (`low` / `medium` / `high`), `missing_questions` (2 max) et `reply` (2-3 phrases dans
  la langue du widget : ce qui est visible, les questions manquantes, l'invitation à laisser prénom et
  téléphone). Métier du prospect (catégorie) dans le contexte. **Jamais de prix** : une réponse ou une
  question contenant un montant (« 250 € », « EUR 250 », « 250,- Euro », « CHF 90 ») est remplacée par
  notre texte, un objet ou un dommage qui en contient est écarté. Verdict lu avec tolérance (`"false"`,
  `0`…) ; absent = non jugé. Modèle indisponible : photo gardée, réponse neutre (`relevant` = `NULL`).
- **Hors sujet** (`relevant` = false) : refus poli, image supprimée de R2 tout de suite (la ligne reste,
  sans lien). Si la suppression échoue, le lien est masqué et la purge réessaie.
- **Journal** : l'échange est ajouté à la conversation de la session (« 📷 Photo envoyée » + réponse),
  donc à la transcription de l'email.
- **Demande** : à la capture, les photos gardées de la visite (24 h) sont liées
  (`ai_assistant_photos.request_id`) et listées dans `photos_json` (`url`, `object`, `damage`, `urgency`,
  3 au plus) ; canal `photo`. Une photo envoyée **après** les coordonnées rejoint la demande encore ouverte
  de la visite (elle apparaît au dashboard et dans le rappel ; l'alerte déjà partie n'est pas renvoyée). Une demande avec
  photos est un **devis** (ou une **urgence** si une photo montre un risque immédiat, `urgency` = `high`) :
  email avec les liens des photos, SMS « … (photo) … » selon les alertes, vignettes dans le dashboard.
- **Rétention** : la boucle horaire de `cleanup_service.py` (étape isolée des autres) supprime de R2 les
  photos de plus de 90 jours et retire leur lien des demandes (les descriptions restent). Page Stockage (admin) : catégorie « Photo de
  devis (assistant) », jours restants avant suppression.

## Alertes au commerçant (`services/ai_assistant/request_alerts.py`)

Seulement pour un assistant **vendu** (`delivered`) ; une démo n'alerte que l'owner (push).

- **Réglages par assistant** (colonnes `alert_*` de `ai_assistants`, `NULL` = valeur par défaut ; le
  dashboard n'envoie que les réglages modifiés), dans « Personnaliser » : mobile du commerçant
  (`alert_phone_e164`, `to_e164_mobile`), SMS oui / non, email oui / non, types qui déclenchent un SMS
  (`alert_sms_types`, défaut : devis, rendez-vous, urgence ; question et autre = email seulement) et plage
  « ne pas déranger » (`alert_quiet_start_hour` → `alert_quiet_end_hour`, défaut 22 h → 8 h, heure de
  Paris ; heures égales = jamais de pause).
- **Numéro d'alerte** : un mobile français (06 / 07) se saisit en national seulement si le prospect est en
  France ; tout autre pays exige le format international (`+352…`, `0032…`), sinon un `621 123 456`
  luxembourgeois ou un `079…` suisse deviendrait le mobile français d'un inconnu. Fixe, format inconnu :
  refusé (422, rien n'est enregistré).
- **Alertée** (`owner_alerted_at`) : posé quand les alertes du commerçant partent, donc seulement pour un
  assistant vendu. Rappel et signal 48 h ne regardent que ces demandes : une demande laissée sur la démo
  avant la vente n'est jamais rappelée au nouveau client.
- **Email** : toutes les demandes (le résumé décrit plus haut), à toute heure.
- **SMS** : 1 segment GSM-7, sans mention STOP (message de service, pas de prospection) mais la liste
  STOP de l'owner est respectée. Texte : « Nouvelle demande de devis (photo) de Marc, 06… : résumé.
  Suivi : demo.dibodev.fr/client/… » (les créneaux souhaités d'un rendez-vous suivent le contact : « 06…, pour
  mar. 22/09 après-midi ») ; le contact reste entier, le résumé est coupé au mot, et le lien
  de l'espace client n'est ajouté que s'il laisse au moins 30 caractères de résumé (le résumé passe avant). Envoyé par le nom d'expéditeur SMS de
  l'owner (Paramètres → Relance SMS) et enregistré dans `sms_messages` sans prospect, avec
  `kind = service` (`SmsService.send_service_message`) : coût suivi sur la page SMS, prospect jamais marqué
  contacté, **hors** plafond journalier de l'automatisation et hors récap quotidien, notification (envoi ou
  accusé de réception) seulement en cas d'échec. Un refus avant l'envoi (pas d'expéditeur, numéro en
  liste STOP…) est inscrit au journal d'activité. Reçue pendant la plage de nuit, la demande garde son
  SMS (`sms_due_at` = fin de la plage) ; la boucle de 5 min l'envoie à l'heure, sauf si la demande a été
  traitée entre-temps. Un SMS en retard de plus de 12 h n'est plus envoyé. `sms_sent_at` est réservé avant
  l'envoi, dans le même `UPDATE` qui vérifie que la demande est encore `new` : jamais deux SMS pour une
  demande, jamais de SMS pour une demande traitée.
- **Rappel J+1** : une demande toujours `new` 24 h après son arrivée reçoit **un seul** rappel
  (`reminder_sent_at`) par les mêmes canaux (email « Rappel : … », SMS « Rappel, en attente depuis le
  23/09 : … » pour les types à SMS), jamais pendant la plage de nuit. Les demandes de plus de 72 h ne sont
  pas rappelées.
- **Signal churn** : une demande d'abonné toujours `new` après 48 h déclenche un push à l'owner
  (« Abonné X : N demandes non traitées depuis 48 h », N = toutes ses demandes en attente depuis 48 h ou
  plus), une fois par demande (`stale_notified_at`), un push par assistant ; une demande de plus de 7 jours
  ne déclenche plus de nouveau push.

## Rapport mensuel (`services/ai_assistant/report_service.py`)

Chaque assistant **vendu** (`delivered`, non supprimé) d'un client qui paie (abonnement `active` ou
`past_due`) reçoit le rapport du mois écoulé, envoyé par sa propre boucle de 10 min (à part des alertes :
un modèle lent ne les retarde pas ; `ai_assistant_report_service.run_loop`) du 1er au 3 du mois à partir
de 8 h, heure de Paris. Une démo ou un client résilié n'en reçoit jamais, relances comprises.

- **Période** : le mois calendaire à l'heure de Paris. Un client qui a payé en cours de mois
  (`activated_at` de l'abonnement en cours, posé au paiement ; `created_at` pour les abonnements payés
  avant cette colonne) est compté à partir de ce jour, donc sans les visites de la démo ; payé dans les
  7 derniers jours du mois, son premier rapport est celui du mois suivant.
- **Chiffres** (`stats_json`, visites et demandes de test exclues) : conversations où un visiteur a écrit
  dans le mois (un visiteur qui revient compte dans chaque mois où il écrit), demandes, devis,
  rendez-vous, urgences, demandes avec photo, demandes marquées traitées et délai moyen avant
  « traitée », % hors horaires parmi les demandes aux horaires connus, langues des conversations
  (`fr-FR` compté `fr`), et les 3 questions les plus posées : le modèle (usage `assistant_report`, EU only
  respecté, 30 s maximum) regroupe le premier message du mois de chaque conversation, à partir de 3
  conversations ; une question qui contient un lien, un email ou un numéro est écartée ; sans réponse du
  modèle, la rubrique est omise.
- **Email** : envoyé depuis l'identité d'envoi de l'owner à l'adresse du commerçant (la même que pour
  les demandes), l'owner en copie cachée, avec le lien de l'espace client ; sans aucune adresse
  commerçant, l'owner seul le reçoit.
  Objet « Sofia en septembre : 43 demandes, 6 rendez-vous, 9 devis, 31 % en dehors de vos horaires ».
  Bandeau à la couleur d'accent du widget (noir si absente ou invalide), texte en noir ou blanc selon la
  couleur, mise en page en tableau et styles inline.
- **Mois sans visite** (aucune conversation, aucune demande) : un autre email (vérifier que la bulle
  apparaît sur le site, que la fiche d'établissement Google renvoie vers le site ; lien vers
  `custom_domain`, sinon le site du prospect, quand il se lit comme un domaine) et un push à l'owner
  « Abonné X : aucune visite en septembre 2026 (risque de désabonnement) » (`is_empty`).
- **Une fois par mois** : la ligne `ai_assistant_reports` (unique par assistant et mois) est écrite avant
  l'envoi et chaque essai y est réservé (`attempts`, `last_attempt_at`) : un rapport ne part jamais deux
  fois. Un envoi en échec est inscrit au journal d'activité et retenté deux fois, à une heure
  d'intervalle au moins, avec les chiffres déjà calculés ; les relances s'arrêtent avec les jours d'envoi
  (le journal dit alors « abandonné »).
- **Drapeau « Risque de churn »** (dashboard, `churn_risk`) : assistant vendu, abonnement actif payé
  depuis plus de 30 jours, aucune conversation ni demande sur les 30 derniers jours (tests exclus).

## Espace client (`services/ai_assistant/client_space_service.py`)

La page `/client/{token}` du demo-host (`demo-host/app/pages/client/[token].vue`), sans compte ni mot de
passe, pour le client d'un assistant **vendu** (`delivered`) ; une démo n'en a pas.

- **Lien magique** (`client_links.py`) : `<id>.<expiration en base 36>.<signature>`, environ 28
  caractères, HMAC-SHA256 tronqué à 96 bits (clé `SECRET_KEY`) de l'assistant et de l'expiration, valable
  30 jours. Aucune table : chaque alerte SMS, chaque email de résumé et chaque rapport mensuel en porte
  un neuf (avec « lien personnel : ne transférez pas cet email tel quel »). Un lien falsifié, non
  canonique, d'un assistant supprimé ou non vendu, n'ouvre rien (404) ; un lien expiré répond 401
  « demandez un nouveau lien » et la page propose de l'envoyer à l'adresse du commerçant (jamais
  affichée), jusqu'à 90 jours après son expiration.
- **Envoi depuis le dashboard** : bouton « Envoyer l'espace client » des cartes vendues (email
  transactionnel depuis l'identité d'envoi de l'owner, adresse du commerçant comme pour les demandes ;
  le lien est aussi copié).
- **Contenu** : toutes les demandes à traiter puis les dernières traitées, 30 au total (tests exclus ;
  coordonnées cliquables, photos, « Marquer traitée »), le dernier rapport mensuel
  (`ai_assistant_reports.stats_json`, avec les phrases de l'email du rapport), les réglages (prénom de
  l'assistant, langues parmi fr / nl / en / de / lu, les autres langues posées par l'owner étant
  gardées, mobile d'alerte, SMS et email oui / non, via le même `ai_assistant_service.update` que le
  dashboard), l'abonnement (prix figé, statut, fin de période, résiliation programmée) avec le portail
  Stripe Billing (`billing_portal.Session.create`, retour sur l'espace ; ses options se règlent dans
  Stripe, Settings → Billing → Customer portal). Section Connexions réservée à l'agenda.
- **Mobile d'alerte** : depuis l'espace, seulement un mobile de France, Belgique, Luxembourg, Suisse ou
  Allemagne ; tout changement est annoncé par email à l'adresse du commerçant (que l'espace ne modifie
  pas, seuls les 2 derniers chiffres y figurent) et inscrit au journal d'activité de l'owner.
- **Résiliation programmée** : `ai_assistant_subscriptions.cancel_at_period_end`, lu sur
  `customer.subscription.updated` (`cancel_at_period_end` ou `cancel_at`) : l'abonnement reste `active`
  jusqu'à la fin de la période payée.
- **Page** : couleur d'accent du client, typographie de `/ia`, `noindex` et `referrer: no-referrer` (le
  jeton ne fuit pas vers les photos ouvertes), pas de suivi PostHog.

## Intégration campagnes

`{lien_assistant}` (résolu vers l'assistant **actif** de l'expéditeur pour ce prospect — jamais celui
d'un autre membre sur un prospect partagé, jamais un assistant vendu ou supprimé — vide sinon) :

- **Email** — `EmailVariables.resolve_assistant_link` : ancre tracée (comme `{lien_demo}`).
- **SMS** — `SmsVariables` : lien nu sans schéma (`EmailVariables.resolve_assistant_url` + `as_sms_link`).
- **Vidéo** — `{lien_video_assistant}` / `{vignette_video_assistant}` (email + SMS) : dégradent en vide
  si la vidéo n'est pas prête (le CTA reste `{lien_assistant}` live).
- **Gardes** — un template qui utilise `{lien_assistant}` ou la vidéo assistant n'est ni mis en file ni
  envoyé sans assistant actif : lancement, ajout de prospects et envoi email (`skipped_no_assistant`,
  motif « Pas d'assistant IA actif »), campagne SMS, relance SMS et composeur SMS. Un assistant généré
  après coup rejoint la file des campagnes actives (`enqueue_ready_prospect`), comme une démo.
- **Module** — une campagne est « assistant » (verrou inter-modules 45 j) dès qu'un de ses templates,
  J1, A/B **ou relance**, utilise une variable assistant, `{prix_assistant}` compris.
- **Durée de vie** — comme un site, la démo compte à rebours `demo_site_ttl_days` (21 j) à partir du
  **premier** email ou SMS qui porte son lien (`demo_link_sent_at` → `expires_at` ; boucle horaire
  `services/ai_assistant/cleanup_service.py` → statut `expired`, page et widget en 404). Un assistant
  vendu ne compte jamais. `{date_expiration}` annonce cette date dans un modèle assistant, et une relance
  programmée après l'expiration est ignorée (« Assistant expiré avant la relance »). Le dashboard affiche
  « En attente d'envoi » puis « Expire dans N j ».

**Modèles de prospection** : 5 emails (`seeders/email_template_seeder.py`, « Assistant IA - … » : réponses
24/7, devis par photo, multilingue, relance, le prix cash) et 5 SMS (`services/sms/templates.py`, clés
`assistant-*`), écrits autour de la demande restée sans réponse (le soir, une photo, la langue du client).
Un seul lien, la démo (`{lien_assistant}`) ; le prix par `{prix_assistant}` ; chaque SMS tient en un segment
GSM-7 mention STOP et prénom compris avec un lien de 45 caractères (testé), sans `https://` (le lien SMS est
nu). Les modèles déjà en base sont réécrits en place par `rewrite_assistant_emails_missed_requests` (sujet,
corps, catégorie, ordre ; « demandes captées » y devient « devis par photo », ou est archivé si ce modèle
existe déjà).

**Page démo** `/ia/{slug}` (`demo-host/app/pages/ia/[slug].vue`) : titre = la promesse (« Plus aucune demande
sans réponse »), trois preuves (répond 24 h/24 dans les langues de l'assistant, devis sur photo, demandes de
rendez-vous), le prix de la démo (`monthly_price_label` de la config publique, mis en forme comme dans les
emails ; masqué une fois vendu et au retour du paiement `?subscribed=1`) et l'invitation à essayer : poser une
question, envoyer une photo, demander un rendez-vous.

Le contact du prospect (email/SMS) bloque l'autre module **45 j** (`services/contact_lock_service.py`),
pour ne pas démarcher deux fois le même prospect entre le site et l'assistant.

Modèles fournis : 5 emails (`seeders/email_template_seeder.py`) et 5 SMS
(`services/sms/templates.py`, famille `assistant-*`, 1 segment GSM-7), dont un modèle **« prix cash »**
franc (prix annoncé, sans engagement).

## Vidéo de prospection

Chaque assistant peut avoir une **vidéo courte** — clip webcam du vendeur en intro/outro, capture du
widget qui répond au milieu — montée par ffmpeg, hébergée sur R2 (`videos/assistant/{slug}.mp4`) et
jouée sur `/va/{slug}` (`demo-host/app/pages/va/[slug].vue`, à l'accent du prospect).

- **Desktop d'abord** (comme le site) : le dashboard build tout sur le PC via le sidecar
  (`/video/build-assistant-full` → `services/assistant_widget_clip_service.py`, capture image-par-image
  avec le Chrome + ffmpeg bundlés), puis `POST /video-final` pousse le résultat sur R2. Le VPS n'est
  jamais touché ; le desktop se release seul (CI Tauri à chaque push).
- **Fallback serveur** (`services/assistant_video_service.py`, Playwright headless) hors desktop ou sur
  échec — l'assistant n'a **aucune** dépendance Storyblok, donc le VPS génère seul.
- **Clip présentateur par module** (`presenter_videos.module = 'ai-assistant'`) : un discours webcam
  « assistant » distinct de celui des sites (Paramètres → Vidéo), avec option de **génération auto** à
  la création de l'assistant (opt-in).
- **Mécanique partagée** avec le site : montage (`services/video_montage.py`), primitives communes
  (`services/video_pipeline.py`), poll/fetch sidecar (`web/app/services/sidecarVideoBuild.ts`).

## Dashboard (module Atelier)

Le **sélecteur de module** (en haut à gauche : Sites web / Assistant IA / Cartes Apple Wallet
verrouillé) échange **toute** la navigation. La nav Assistant IA : Tableau de bord, Mes prospects,
Carte, **Assistants IA**, Campagnes, emails, sms, Ventes (pas de Sites démo ni Automatisations).

La page **Assistants IA** (`web/app/pages/dashboard/ai-assistants.vue`) : KPIs (assistants actifs,
demandes à traiter, dernière demande), cartes par assistant (langues, demandes 7 j / 30 j, % hors
horaires, conversations 7 j, Voir la démo, Copier le script, Personnaliser, Régénérer, Supprimer,
**Générer / Voir la vidéo**) et la section **Demandes** (onglets « À traiter » / « Toutes » ; type,
hors horaires, photos, test, statut ; résumé ; « Marquer traitée », « Sans suite », « Rouvrir »).
Une carte d'abonné silencieux depuis 30 jours porte le badge « Risque de churn ». Une carte vendue a le
bouton « Envoyer l'espace client ».
« Personnaliser » porte aussi les alertes au commerçant (mobile, SMS / email, types à SMS, plage de
nuit). Le clip présentateur « assistant » s'enregistre dans **Paramètres → Vidéo**
(`web/app/components/settings/AssistantPresenterClipCard.vue`). Le `ProspectDrawer` génère / ouvre
l'assistant depuis un prospect selon le module actif.

## Tracking (PostHog, côté demo-host)

Émis par le widget : `assistant_opened`, `assistant_message_sent`, `assistant_lead_submitted` ; la page
vidéo `/va/{slug}` émet `assistant_video_play` / `assistant_video_cta_click`. Tous portent la
super-propriété **`surface: 'assistant'`** (le site porte `surface: 'demo'`), pour distinguer les
modules dans le même projet PostHog. **Aucun** event côté dashboard (non instrumenté — voir la mémoire).

## Carte des fichiers

| Rôle | Fichier |
|---|---|
| Modèle | `api/models/ai_assistant.py`, `api/models/ai_assistant_request.py`, `api/models/ai_assistant_photo.py`, `api/models/ai_assistant_report.py` (+ `ai_assistant_lead.py` historique) |
| Demandes (capture, suivi, compteurs) | `api/services/ai_assistant/request_service.py` |
| Typage + résumé d'une demande | `api/services/ai_assistant/request_analyzer.py` |
| Email de résumé + lien signé | `api/services/ai_assistant/request_email.py`, `api/services/ai_assistant/request_links.py` |
| Reprise des annonces perdues + alertes différées (boucle) | `api/services/ai_assistant/request_runner.py` |
| Rapport mensuel (boucle, chiffres, envoi, drapeau churn) + son email | `api/services/ai_assistant/report_service.py`, `api/services/ai_assistant/report_email.py` |
| Espace client (lien magique, lecture, réglages, portail Stripe) + son email | `api/services/ai_assistant/client_space_service.py`, `client_links.py`, `client_space_email.py`, `api/api/v1/routes/ai_assistant_client_space.py` |
| Page espace client | `demo-host/app/pages/client/[token].vue`, `demo-host/app/components/ClientSpace*.vue` |
| Devis par photo (réception, vision, rattachement, purge) | `api/services/ai_assistant/photo_service.py` |
| Routage des modèles (Mistral, secours Groq, EU only, coûts) | `api/services/ai_assistant/llm_router.py`, `api/services/mistral_service.py` |
| Bench des modèles | `api/scripts/bench_assistant_llm.py` |
| Alertes au commerçant (email, SMS, rappel, signal 48 h) | `api/services/ai_assistant/request_alerts.py` |
| Horaires d'ouverture (hors horaires) | `api/services/ai_assistant/opening_hours.py` |
| Créneaux d'une demande de rendez-vous (sans agenda) | `api/services/ai_assistant/appointment_slots.py` |
| Service génération / edit / régé | `api/services/ai_assistant/assistant_service.py` |
| Config (accent, langues, persona) | `api/services/ai_assistant/config_builder.py` |
| Fiche de connaissance | `api/services/ai_assistant/knowledge_builder.py` |
| Réponse groundée | `api/services/ai_assistant/chat_service.py` |
| Routes | `api/api/v1/routes/ai_assistants.py` |
| Rate limiter | `api/services/rate_limiter.py` |
| Variables campagne | `api/services/email_variables.py`, `api/services/sms_variables.py` |
| Verrou inter-modules | `api/services/contact_lock_service.py` |
| Vidéo (serveur / VPS) | `api/services/assistant_video_service.py` |
| Vidéo (capture desktop) | `api/services/assistant_widget_clip_service.py`, `api/scraper_sidecar.py` |
| Vidéo (commun site + assistant) | `api/services/video_pipeline.py`, `api/services/video_montage.py`, `web/app/services/sidecarVideoBuild.ts` |
| Widget | `demo-host/app/components/AssistantChat.vue` |
| Page de démo | `demo-host/app/pages/a/[slug].vue` |
| Page vidéo | `demo-host/app/pages/va/[slug].vue` |
| Page embed | `demo-host/app/pages/embed/[slug].vue` |
| Loader embed | `demo-host/public/ai-assistant.js` |
| Dashboard | `web/app/pages/dashboard/ai-assistants.vue`, `web/app/utils/dashboardModules.ts` |
| Clip présentateur (réglages) | `web/app/components/settings/AssistantPresenterClipCard.vue` |

## Vente par abonnement (increment C3)

La vente du module est un **abonnement Stripe récurrent**, distinct de la vente de site à 500 € en une
fois (`docs/STRIPE_SETUP.md`). Décidé + implémenté :

- **Prix configurable** par utilisateur : mensuel (`users.assistant_monthly_price_cents`, défaut 79 €,
  conseillé 79 à 99 €) + mois offerts sur l'annuel (`assistant_annual_free_months`, défaut 2 → 790 €/an).
  Les comptes restés sur l'ancien défaut (29 €) passent à 79 € (`raise_assistant_default_price`) ; les
  abonnements en cours gardent leur prix ; la migration affiche les comptes déplacés. La page `/ia` d'une démo
  affiche ce prix (`monthly_price_label` de la config publique, absent une fois l'assistant vendu). `AssistantPricingService`,
  éditable dans **Paramètres → Facturation**, affiché via `{prix_assistant}`.
- **Grandfathering** : le prix est **verrouillé** sur la ligne `ai_assistant_subscriptions.amount_cents`
  à la souscription — monter le prix configuré ne touche jamais un abonné existant.
- **Lien d'abonnement permanent** : l'owner copie depuis le dashboard
  (`GET /ai-assistants/{id}/subscription/link?interval=month|year`) un lien vers l'endpoint public
  `GET /ai-assistants/public/{slug}/subscribe`, qu'il envoie au client. À chaque clic, cet endpoint crée
  une Checkout Session Stripe **fraîche** (`mode=subscription`, compte Stripe **plateforme**) et redirige :
  une session expire en 24 h, le lien envoyé jamais. La ligne locale `INCOMPLETE` est réutilisée d'un
  clic à l'autre (prix du moment tant que rien n'est payé), purgée après 7 j sans paiement (boucle
  `services/ai_assistant/cleanup_service.py`) ; 5 clics / 5 min par visiteur. Un assistant déjà vendu
  renvoie vers sa page. Le webhook (`/payments/webhook`) active la ligne sur
  `checkout.session.completed` et synchronise le statut sur `customer.subscription.updated/deleted`.
- **À l'activation** : l'assistant passe `DELIVERED` (sorti du TTL démo, jamais coupé tant que le client
  paie) — une démo **expirée** est ainsi ravivée par le paiement. `activated_at` garde l'heure du premier
  paiement (le début du service, pour le rapport mensuel et le drapeau churn).
- **Essai** = la démo (limitée par `expires_at`) ; pas d'essai gratuit du produit. Résiliation libre,
  zéro frais ; satisfait-remboursé 1er mois : bouton « Rembourser » (dernière facture, PaymentIntent lu via
  `payments.data.payment.payment_intent` — API Stripe 2025-03-31 — avec repli sur la charge de la facture).

⚠️ **À vérifier en Stripe test mode avant la prod** (non testable hors ligne) : le flux checkout + webhook
de bout en bout, et **ajouter les événements** `customer.subscription.updated` / `customer.subscription.deleted`
à l'endpoint webhook Stripe. Multi-tenant plus tard → passer du compte plateforme au compte **connecté**
de chaque user (Stripe Connect + application fee), comme la facture du site.

Fichiers : `api/services/assistant_subscription_service.py`, `api/models/ai_assistant_subscription.py`,
`api/enums/assistant_subscription_status.py`, `api/services/assistant_pricing_service.py`.

## Statuts servis publiquement

Les endpoints publics (`/ai-assistants/public/{slug}` : config, chat, lead, intérêt) servent un assistant
`active` (la démo) **ou** `delivered` (vendu, intégré sur le site du client). Un assistant `expired`,
`failed` ou supprimé répond 404.
Le bandeau de contact de la page hébergée ne s'affiche que sur la démo (`active`).
