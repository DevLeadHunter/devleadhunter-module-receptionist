# Module Assistant IA — DevLeadHunter

> Comment est généré, servi, personnalisé et vendu l'**assistant IA** — le réceptionniste
> conversationnel généré par prospect, multilingue, à la marque du prospect. Ce document est la
> **source de vérité** du module (le 2ᵉ produit vendable, à côté du module Sites web).

## TL;DR

- **1 assistant = 1 prospect.** Généré depuis les mêmes données que la démo de site (enrichissement),
  servi publiquement par `slug`, il répond aux visiteurs **strictement** sur la base de sa fiche de
  connaissance (`knowledge_json`) — jamais d'invention.
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

## Endpoints (`api/api/v1/routes/ai_assistants.py`)

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/ai-assistants` | Générer un assistant pour un prospect |
| `GET` | `/ai-assistants` | Lister ses assistants (filtre `?prospect_id=`) |
| `GET` | `/ai-assistants/leads` | Lister les contacts captés (join assistant) |
| `PATCH` | `/ai-assistants/{id}` | Personnaliser (nom, persona, langues, accent) |
| `POST` | `/ai-assistants/{id}/regenerate` | Régénérer la connaissance (garde marque + slug) |
| `POST` | `/ai-assistants/{id}/video` | Générer la vidéo de prospection (fond serveur / VPS) |
| `GET` | `/ai-assistants/{id}/video-context` | Contexte pour le build desktop (sidecar) |
| `POST` | `/ai-assistants/{id}/video-final` | Recevoir la vidéo montée sur le PC → R2 |
| `DELETE` | `/ai-assistants/{id}/video` | Supprimer la vidéo générée |
| `DELETE` | `/ai-assistants/{id}` | Supprimer (soft-delete) |
| `GET` | `/ai-assistants/public/{slug}` | Config publique du widget (+ vidéo si prête) |
| `POST` | `/ai-assistants/public/{slug}/chat` | Réponse groundée à un message |
| `POST` | `/ai-assistants/public/{slug}/lead` | Capturer un contact |
| `POST` | `/ai-assistants/public/{slug}/interest` | Signaler l'intérêt de l'owner (pop-up « me contacter ») |

Les 3 endpoints publics sont **rate-limités par IP** (`services/rate_limiter.py`) : chat 30 / 300 s,
lead 8 / 300 s (fenêtre glissante en mémoire).

## Le widget (`demo-host/app/components/AssistantChat.vue`)

C'est le **produit** que le client colle sur son site. Il porte :

- **5 langues d'interface** (FR / NL / DE / EN / LU) : accueil, suggestions, placeholder, libellés du
  formulaire de rappel, réponse de secours — un jeu complet par langue.
- **Ouverture dans la langue du visiteur** : au montage, la langue du navigateur est choisie si
  l'assistant l'offre (sinon FR). Le visiteur peut changer ; le chat répond toujours dans **sa** langue.
- **Persistance de conversation** : la conversation (et la langue) est gardée en `localStorage`
  (`dlh-assistant-<slug>`, bornée à 40 messages) — un visiteur qui recharge ou change de page **retrouve
  son fil**. Écriture/lecture en `try/catch` (mode privé) : le widget marche sans.
- **Capture de lead** : nom + contact + besoin + langue → notification à l'owner.
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

Le script monte un iframe transparent (bas-droite) vers `/embed/{slug}`, se redimensionne au
`postMessage` du widget, ne touche à aucun style de la page hôte, sans dépendance.

## Intégration campagnes

`{lien_assistant}` (résolu vers l'assistant **actif** du prospect, vide sinon) :

- **Email** — `EmailVariables.resolve_assistant_link` : ancre tracée (comme `{lien_demo}`).
- **SMS** — `SmsVariables` : lien nu sans schéma (`EmailVariables.resolve_assistant_url` + `as_sms_link`).
- **Vidéo** — `{lien_video_assistant}` / `{vignette_video_assistant}` (email + SMS) : dégradent en vide
  si la vidéo n'est pas prête (le CTA reste `{lien_assistant}` live), pas de garde à l'enqueue.

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
contacts captés, dernier contact), cartes par assistant (langues, badge de contacts captés, Voir la
démo, Copier le script, Personnaliser, Régénérer, Supprimer, **Générer / Voir la vidéo**) et la liste
des contacts. Le clip présentateur « assistant » s'enregistre dans **Paramètres → Vidéo**
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
| Modèle | `api/models/ai_assistant.py`, `api/models/ai_assistant_lead.py` |
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

- **Prix configurable** par utilisateur : mensuel (`users.assistant_monthly_price_cents`, défaut 29 €)
  + mois offerts sur l'annuel (`assistant_annual_free_months`, défaut 2 → 290 €/an). `AssistantPricingService`,
  éditable dans **Paramètres → Facturation**, affiché via `{prix_assistant}`.
- **Grandfathering** : le prix est **verrouillé** sur la ligne `ai_assistant_subscriptions.amount_cents`
  à la souscription — monter le prix configuré ne touche jamais un abonné existant.
- **Checkout** : l'owner génère un lien Stripe (`POST /ai-assistants/{id}/subscription/checkout?interval=month|year`,
  `mode=subscription`, compte Stripe **plateforme**) depuis le dashboard et l'envoie au client, qui
  s'abonne sur la page hébergée Stripe. Le webhook (`/payments/webhook`) active la ligne sur
  `checkout.session.completed` et synchronise le statut sur `customer.subscription.updated/deleted`.
- **À l'activation** : l'assistant passe `DELIVERED` (sorti du TTL démo, jamais coupé tant que le client paie).
- **Essai** = la démo (déjà limitée par `expires_at`) ; pas d'essai gratuit du produit. Résiliation libre,
  zéro frais ; satisfait-remboursé 1er mois = politique (remboursement manuel Stripe).

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
