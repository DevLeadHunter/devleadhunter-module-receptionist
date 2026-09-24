# Passation — Réceptionniste IA, phase 1 (modèle économique)

Branche **`feat/receptionist-phase-1`** : un commit par ticket (6), plus celui de ce document, posés
sur `main` à `a0e6205`. `origin/main` n'a pas bougé depuis : la branche passe en avance rapide, sans
conflit. Rien n'est mergé, `main` n'a pas été poussé.

| Ticket | Asana | Commit | État |
|---|---|---|---|
| R3 — demandes structurées + email de résumé + boîte de réception | 1218810013765436 | `3caa9c2` | livré |
| R10 — alertes au commerçant (SMS / email, nuit, rappel J+1, signal 48 h) | 1218810158812114 | `f2908bc` | livré |
| R6 — devis par photo | 1218810139834916 | `1d62798` | livré |
| R4 — Mistral d'abord, secours Groq journalisé, « EU only » | 1218810158843341 | `0a65ac3` | livré ; en attente de la clé Mistral et des CGU |
| R11 — 79 €, 5 emails + 5 SMS de prospection, textes de /ia | 1218810139755803 | `e46cf0a` | livré (périmètre prix / modèles / page) |
| R9 — rapport mensuel au client + drapeau churn | 1218810013839351 | `d38c6fa` | livré (sans la page espace client) |
| R8, R2, R1 | — | — | non commencés (voir la fin) |

Chaque ticket a reçu sur Asana un commentaire « fait / reste / comment tester ». La documentation
fonctionnelle à jour est dans `docs/ASSISTANT_MODULE.md` (sections Journal des conversations, Demandes,
Modèles IA, Devis par photo, Alertes au commerçant, Rapport mensuel, Vente par abonnement).

Hors de cette branche : R12 (verticales, détection « déjà équipé », score « demande entrante ») est sur
`claude/epic-bohr-lgv8d8`, 4 commits, lui non plus pas mergé.

## Rejouer

```bash
cd api
python migrations/run_migrations.py      # idempotent ; les 9 migrations de la phase 1 sont listées plus bas
python -m pytest -q                      # attendu : 1006 passed, 3 failed (préexistants, voir plus bas)
ruff format --check . && ruff check .    # attendu : propre
cd ..
npm --prefix web run lint                # prettier + eslint propres ; typecheck : 5 erreurs préexistantes
npm --prefix demo-host run lint          # prettier + eslint propres ; typecheck : 2 erreurs préexistantes
```

Migrations de la phase 1, dans l'ordre de `MIGRATION_MODULES` :

1. `add_ai_assistant_requests_table` (R3) : table `ai_assistant_requests` et recopie unique des anciens leads.
2. `add_ai_assistant_alerts` (R10) : colonnes `alert_*` de `ai_assistants`, colonnes d'alerte des demandes, `sms_messages.kind`.
3. `add_ai_assistant_photos_table` (R6) : table `ai_assistant_photos`.
4. `add_ai_assistant_eu_only` (R4) : colonne `ai_assistants.eu_only`.
5. `raise_assistant_default_price` (R11) : les comptes restés sur l'ancien défaut 29 € passent à 79 € (elle affiche lesquels).
6. `rewrite_assistant_emails_missed_requests` (R11) : réécrit les 5 modèles email « Assistant IA » en base.
7. `add_ai_assistant_conversations_is_test` (R9) : colonne `ai_assistant_conversations.is_test`.
8. `add_assistant_subscription_activated_at` (R9) : colonne `ai_assistant_subscriptions.activated_at`.
9. `add_ai_assistant_reports_table` (R9) : table `ai_assistant_reports`.
10. `add_assistant_subscription_cancel_at_period_end` (R8) : colonne `ai_assistant_subscriptions.cancel_at_period_end`.

Tests par ticket (depuis `api/`, avec `python -m pytest -q`) :

| Ticket | Fichiers | Tests |
|---|---|---|
| R3 | `tests/test_assistant_requests.py tests/test_assistant_opening_hours.py tests/test_assistant_request_analysis.py tests/test_ai_assistant_service.py` | 17 + 16 + 11 + 8 |
| R10 | `tests/test_assistant_request_alerts.py` | 18 |
| R6 | `tests/test_assistant_photos.py` | 15 |
| R4 | `tests/test_assistant_llm_router.py tests/test_ai_assistant_chat.py` | 15 + 6 |
| R11 | `tests/test_assistant_sales_copy.py tests/test_sms_templates.py tests/test_assistant_pricing.py` | 8 + 23 + 5 |
| R9 | `tests/test_assistant_reports.py tests/test_ai_assistant_conversations.py` | 26 + 5 |

Échecs et erreurs **préexistants**, identiques sur `main` à `a0e6205` (revérifié sur un worktree de
`main`) :

- `tests/test_sms_auto_planning.py::test_slots_already_planned_keep_their_capacity_reserved` dépend de la date du jour.
- `tests/test_storyblok_space_swap.py::test_swap_needed_when_trial_would_end_before_demo_ttl` et `::test_boundary_exactly_enough_trial_remaining`.
- Typecheck `web` : 5 erreurs, `demo-host` : 2 erreurs. Ce sont des chemins Windows absolus (`C:/Users/…`) dans les types générés, plus un type PostHog. Aucune nouvelle erreur.

Environnement de ce poste : pas de navigateur de test branché sur l'app, pas de clés Mistral / Groq /
smsmode / Resend. Tout ce qui touche un service externe est testé avec des doublures. Les écrans ont été
relus dans le code, pas cliqués.

---

## R3 — Demandes structurées (`3caa9c2`)

**Fichiers**
- API :
  - `models/ai_assistant_request.py`, `enums/ai_assistant_request.py`
  - `services/ai_assistant/request_service.py`, `request_analyzer.py`, `request_email.py`, `request_links.py`, `request_runner.py`, `opening_hours.py`
  - `services/notification_service.py`, `services/text_normalizer.py`, `services/trade_normalizer.py`
  - `api/v1/routes/ai_assistants.py` (liste et mise à jour des demandes, lien « marquer traitée » en GET de confirmation puis POST), `schemas/ai_assistant.py`
  - `main.py` (boucle), `migrations/add_ai_assistant_requests_table.py`
- Web : `pages/dashboard/ai-assistants.vue` (section Demandes, KPI), `services/aiAssistantService.ts`, `types/AiAssistant.ts`.
- Widget : `demo-host/app/components/AssistantChat.vue` envoie `session_id` et `internal` avec la demande.

**Vérifié (tests)**
- Capture et rattachement à la conversation du journal.
- Une demande par session : un 2ᵉ envoi met à jour la même demande.
- Une demande traitée, ou de plus de 24 h, n'est jamais rouverte.
- Typage et résumé par le modèle, repli par mots-clés FR / NL / DE / EN.
- Hors horaires calculé sur les horaires Google (heure de Paris) ; inconnu sans horaires.
- Annonce unique (réservation atomique) et reprise par la boucle.
- Lien signé : le GET ne fait qu'afficher, le POST agit.
- Migration des anciens leads : une seule fois, comme historique traité.
- Échappement HTML de l'email.

**Non vérifié** : écrans du dashboard dans un navigateur, envoi réel de l'email.

**Décisions prises seul**
- Email de résumé seulement pour un assistant **vendu** (`delivered`) ; R10 applique la même règle aux SMS et aux rappels. Une démo n'écrit jamais au prospect ; seul l'opérateur reçoit un push.
- Une visite `?internal=1` crée une demande `is_test` : jamais annoncée, hors compteurs et hors « À traiter ».
- Annonce au plus une fois ; la boucle de 5 min reprend les demandes de 2 min à 24 h qu'un redémarrage a perdues.
- Le scoring prospect (`behavior_service`) ne lisait déjà pas les leads de l'assistant. R3 ne le dégrade pas, mais ne le branche pas non plus.

---

## R10 — Alertes au commerçant (`f2908bc`)

**Fichiers**
- API :
  - `services/ai_assistant/request_alerts.py` : `AlertSettings`, `QuietHours`, `AlertSms`, `AiAssistantRequestAlerts`
  - `services/sms/phone_normalizer.py` (déplacé en feuille pour casser un import circulaire), `services/sms_service.py` (`send_service_message`)
  - `services/sms_automation_service.py` et `api/v1/routes/sms.py` : le SMS de service est exclu du plafond et du récap
  - `enums/sms_message_kind.py`, `models/sms_message.py` (`kind`), `models/ai_assistant.py` (`alert_*`), `models/ai_assistant_request.py`
  - `migrations/add_ai_assistant_alerts.py`, `schemas/ai_assistant.py`, `api/v1/routes/ai_assistants.py`
- Web : modale « Personnaliser » (bloc alertes, n'envoie que les champs modifiés).

**Vérifié (tests)**
- Réglages par défaut et numéro d'alerte (national accepté seulement pour un commerce en France).
- Plage de nuit : une demande de devis à 22 h donne push et email tout de suite, SMS à 8 h, et aucun SMS si elle a été traitée entre-temps.
- SMS d'un seul segment GSM-7, exclu du plafond et du récap.
- Rappel J+1 unique, jamais la nuit, jamais pour une demande laissée sur la démo.
- Push 48 h unique par demande.
- Réservations atomiques (jamais deux SMS pour une même demande).

**Non vérifié** : envoi réel smsmode, écran Personnaliser dans un navigateur.

**Décisions prises seul**
- SMS de service sans mention STOP (ce n'est pas de la prospection), mais la liste STOP de l'owner est respectée. Notification seulement en cas d'échec.
- `owner_alerted_at` conditionne rappel et push 48 h : une demande laissée pendant la démo n'est jamais rappelée au client.
- Pas de rappel au-delà de 72 h. Un SMS retenu la nuit et en retard de plus de 12 h n'est plus envoyé. Pas de nouveau push 48 h pour une demande de plus de 7 jours.
- Adresse du commerçant : celle de l'assistant, sinon celle du prospect, sinon (depuis R9) l'email saisi par le client au paiement Stripe de l'abonnement en cours.

---

## R6 — Devis par photo (`1d62798`)

**Fichiers**
- API :
  - `services/ai_assistant/photo_service.py`, `models/ai_assistant_photo.py`, `enums/ai_assistant_photo.py`, `migrations/add_ai_assistant_photos_table.py`
  - route `POST /ai-assistants/public/{slug}/photo` (lecture manuelle du multipart, taille vérifiée avant lecture)
  - `services/rate_limiter.py`, `services/r2_storage_service.py`, `services/ai_assistant/cleanup_service.py` (purge)
  - `request_service.attach_late_photos` ; `api/v1/routes/admin_storage.py` (catégorie « Photo de devis »)
- Widget : `demo-host/app/utils/PhotoCompressionUtils.ts`, panneau photo de `AssistantChat.vue`.
- Web : vignettes dans les demandes, page Stockage.

**Vérifié (tests)**
- Ré-encodage JPEG sans métadonnées ; refus au-delà de 8 Mo, 50 Mpx, 3 photos par session et de la limite par visiteur.
- Photo hors sujet supprimée de R2 tout de suite.
- Aucun prix dans la réponse ni dans la description (regex `PRICE_PATTERN` : €, EUR, CHF, « 250,- Euro »…).
- Type devis, ou urgence si la photo montre un risque immédiat.
- Photo envoyée après les coordonnées : rattachée à la demande ouverte.
- Purge à 90 jours.

**Non vérifié** : vrai modèle vision, compression dans un vrai navigateur, iPhone (HEIC).

**Décisions prises seul**
- La photo n'entre jamais dans l'historique du chat. Seule une ligne « 📷 Photo envoyée » est journalisée.
- Une photo HEIC que le navigateur ne sait pas convertir est refusée proprement : pas de décodeur HEIC côté serveur.
- Les vignettes du dashboard chargent l'image entière (pas de miniature stockée).

---

## R4 — Mistral d'abord, Groq en secours (`0a65ac3`)

**Fichiers**
- API :
  - `services/mistral_service.py`, `services/ai_assistant/llm_router.py`, `enums/assistant_llm.py`
  - `core/config.py` (modèles et prix Mistral / Groq), `.env.example`
  - `models/ai_assistant.py` (`eu_only`), `migrations/add_ai_assistant_eu_only.py`
  - `chat_service.py`, `photo_service.py`, `request_analyzer.py` passent par le routeur
  - `main.py` : logger du routeur en INFO
  - `scripts/bench_assistant_llm.py`
- Web : case « EU only » dans Personnaliser.

**Vérifié (tests, fournisseurs simulés)**
- Mistral en premier pour le chat, les photos et l'analyse des demandes.
- Secours Groq journalisé, alerte aux admins limitée à une toutes les 30 min par usage et par type de panne.
- Un assistant EU only n'atteint jamais Groq, pour les 4 usages.
- Sans clé Mistral : tout reste sur Groq, sauf EU only (sans réponse, avec une alerte).
- Une requête refusée par Mistral (4xx) ne compte pas comme une panne.
- Client Mistral testé par `httpx.MockTransport` : mode JSON, lecture du texte et de l'usage, relance sur 429.

**Non vérifié** : vraie API Mistral, bench non lancé (pas de clés).

**Décisions prises seul**
- Budget de temps partagé : Mistral a la moitié du délai quand un secours existe ; un appel EU only a tout le délai et une relance rapide.
- `eu_only` refusé (422) tant que `MISTRAL_API_KEY` n'est pas configurée.
- Une ligne `assistant_llm_call` par appel (fournisseur, modèle, latence, tokens, coût estimé, secours, EU only), en INFO.
- Pas de mention « données hébergées en Europe » sur /ia.

---

## R11 — Prix et textes de vente (`e46cf0a`)

**Fichiers**
- API :
  - `services/assistant_pricing_service.py` (défaut 7 900 centimes), `models/user.py`, `schemas/user.py`
  - `migrations/raise_assistant_default_price.py`, `migrations/rewrite_assistant_emails_missed_requests.py`
  - `seeders/email_template_seeder.py` (5 emails), `services/sms/templates.py` (5 SMS, mêmes clés)
  - réponse publique `monthly_price_label`
- Demo-host : `pages/ia/[slug].vue` (titre, 3 preuves, prix), `types/AiAssistant.ts`.
- Web : `pages/dashboard/settings/billing.vue` (« Conseillé : 79 à 99 €/mois »).

**Vérifié (tests)**
- Défaut 79 € (annuel 790 €).
- Migration du prix idempotente, qui ne touche que l'ancien défaut.
- Réécriture des emails en place, et archivage de l'ancien quand le nouveau existe déjà.
- Chaque email ne contient qu'un lien (la démo), le prix via `{prix_assistant}`, ni tiret long ni `http`.
- Chaque SMS tient en un segment avec un lien de 45 caractères.
- Le prix apparaît sur une démo, jamais sur un assistant vendu.

**Non vérifié** : rendu de /ia et des aperçus de campagne dans un navigateur.

**Décisions prises seul**
- Le modèle « demandes captées » est renommé en place en « devis par photo » : les campagnes gardent leur modèle.
- Le prix est masqué une fois l'assistant vendu et au retour du paiement.
- « Premier mois satisfait ou remboursé » figure dans le texte (email « prix cash », /ia), comme le demande le ticket. Rien n'est automatique côté Stripe : le remboursement est manuel.
- Le nom du module n'a pas changé.

---

## R9 — Rapport mensuel (`d38c6fa`)

**Fichiers**
- API :
  - `services/ai_assistant/report_service.py` (boucle, chiffres, envoi, relances, drapeau churn), `report_email.py` (rendu)
  - `models/ai_assistant_report.py` + migration
  - `models/ai_assistant_conversation.py` (`is_test`) + migration
  - `models/ai_assistant_subscription.py` (`activated_at`) + migration, posé dans `assistant_subscription_service.activate_from_session`
  - `enums/assistant_subscription_status.py` (`LIVE_SUBSCRIPTION_STATUSES`)
  - `conversation_service.py` : compteurs par dernier message, tests exclus
  - `request_alerts.business_email` : public, repli sur l'email Stripe
  - `notification_service.notify_assistant_inactive`
  - `french_date_formatter.month_year`, `knowledge_builder.LANGUAGE_NAMES` (rendu public), `assistant_service.accent_color`
  - `api/v1/routes/ai_assistants.py` (`churn_risk` ; les routes régénérer et vidéo renvoient la carte complète), `main.py` (boucle)
- Widget : `AssistantChat.vue` envoie `internal` avec chaque message du chat.
- Web : badge « Risque de churn » (noir et blanc), type `churn_risk`.

**Vérifié (tests, 26)**
- Bornes du mois à l'heure de Paris (heure d'été et d'hiver).
- Chiffres exacts sur des données semées : visiteur qui revient, tests, autres mois et autre assistant exclus, langues (`lu`), délai de traitement, questions.
- Envoi unique avec l'owner en copie cachée ; fenêtre du 1er au 3 dès 8 h, rattrapage.
- Mois vide : email de vérifications et push.
- Pas de rapport pour une démo, un client résilié, un assistant supprimé ou un paiement dans la dernière semaine.
- Client payé en cours de mois : compté depuis le paiement, même si la ligne d'abonnement a été créée plus tôt.
- `activated_at` posé même si les événements Stripe arrivent dans le désordre.
- Relances : 3 essais à une heure d'intervalle, « abandonné » après le 3, jamais vers un client résilié entre-temps.
- Questions contenant un lien ou un contact écartées.
- Drapeau churn dans la liste ; chat `internal` journalisé en test ; migrations rejouables.
- Rendu vérifié dans Chromium à 375 px et 640 px (tableau de chiffres, bandeau d'accent, version vide).

**Non vérifié** : rendu réel dans Gmail et sur iPhone, envoi réel, vrai modèle pour les questions.

**Décisions prises seul**
- Destinataires : seulement les assistants vendus dont l'abonnement est actif ou en relance de paiement (`active`, `past_due`).
- Période : le client est compté à partir de son paiement (`activated_at` ; `created_at` pour les abonnements payés avant cette colonne). Payé dans les 7 derniers jours du mois : premier rapport le mois suivant.
- Une conversation compte dans chaque mois où le visiteur écrit. Les compteurs 7 j / 30 j du dashboard suivent maintenant le dernier message (et non plus le début) et excluent les tests.
- Les visites `?internal=1` du chat sont marquées `is_test` (le widget envoie `internal`). Elles restent visibles dans le journal, sans marque à l'écran.
- « Temps de réponse moyen » est lu comme le délai avant « traitée » : le temps de réponse de l'assistant n'est pas stocké.
- Les 3 questions les plus posées sont lues par le modèle (usage `assistant_report`, EU only respecté, 30 s), à partir de 3 conversations.
- Mois sans visite : l'email renvoie vers le site du client (`custom_domain`, sinon le site du prospect), pas vers /ia, qui est la page de vente.
- Envoi au plus une fois : 3 essais, journal d'activité à chaque échec, arrêt à la fin des jours d'envoi.
- Drapeau churn : assistant vendu, abonnement actif payé depuis plus de 30 jours, rien sur 30 jours.

---

## R8 — Espace client par lien magique

**Fichiers**
- API :
  - `services/ai_assistant/client_links.py` : jeton `<id>.<expiration base 36>.<signature>` (~28 caractères, HMAC-SHA256 tronqué à 96 bits), forme canonique stricte
  - `services/ai_assistant/client_space_service.py` (lecture, « traitée », réglages, portail Stripe, envoi du lien, avis de changement du mobile), `client_space_email.py`
  - `api/v1/routes/ai_assistant_client_space.py` (routes publiques `/ai-assistants/client/{token}…`), route owner `POST /ai-assistants/{id}/client-link` dans `ai_assistants.py`
  - `schemas/ai_assistant_client_space.py`, `enums/assistant_widget_language.py`, `services/rate_limiter.py` (3 limiteurs)
  - `assistant_subscription_service.billing_portal_url` ; `cancel_at_period_end` (modèle, migration, webhook)
  - Lien branché dans le SMS d'alerte (`AlertSms._fit` : résumé d'abord, lien si ≥ 30 caractères de résumé), l'email de résumé et le rapport mensuel (`AiAssistantRequestEmail.paragraph/button/document/client_space_note`, partagés)
  - `client_ip`, `business_country` rendus publics (réutilisés)
- Demo-host : `pages/client/[token].vue`, `components/ClientSpaceRequests.vue`, `ClientSpaceReport.vue`, `ClientSpaceSettings.vue`, types.
- Web : bouton « Envoyer l'espace client » (cartes vendues), `AiAssistantService.issueClientLink`.

**Vérifié**
- Tests (14) : jeton (falsifié, non canonique, expiré), isolation entre assistants, 401 / 404, réglages (langues de l'owner gardées, null ignoré), mobile invalide ou hors zone refusé, avis de changement du mobile (email + journal), portail Stripe et URL de retour, renouvellement (3 / h, 90 jours max après expiration), lien owner (vendu seulement, scopé), date d'expiration en heure de Paris, SMS (résumé avant lien, 1 segment), résiliation programmée lue depuis Stripe.
- Navigateur (Chromium, API locale sur SQLite + `nuxt dev`) : page complète à 390 et 1280 px, « Marquer traitée », enregistrement des réglages, mobile refusé avec le message de l'API, portail indisponible sans Stripe, page « lien expiré » et demande d'un nouveau lien.

**Non vérifié** : vrai portail Stripe (clé et configuration du portail absentes ici), envoi réel des emails, SMS réel avec le lien.

**Décisions prises seul**
- Pas de table : le lien est sans état (HMAC + expiration 30 jours) et chaque alerte en apporte un neuf. Pas de révocation individuelle (voir questions).
- Espace réservé aux assistants vendus ; le lien owner est refusé pour une démo.
- La page se charge dans le navigateur (`server: false`) : la limite par IP vise le visiteur, pas le serveur Vercel.
- Depuis l'espace, le mobile d'alerte doit être FR / BE / LU / CH / DE et tout changement est annoncé à l'adresse du commerçant (non modifiable depuis l'espace) et à l'owner.
- Liste : toutes les demandes à traiter d'abord, puis les dernières traitées (30 au total).
- Les phrases du rapport (langues, délai) viennent de l'API, identiques à l'email.
- La page vit sur le demo-host comme demandé ; ses appels sont publics par lien signé (pas d'authentification), comme ceux du widget. Les standards du demo-host interdisent « appels API authentifiés / privés » : exception à acter.

---

## Questions pour Léo

1. **Mistral** :
   - Valider les CGU / DPA (région, rétention, pas d'entraînement), créer `MISTRAL_API_KEY`, puis lancer `python scripts/bench_assistant_llm.py` en prod (objectif ≤ 0,02 € par conversation).
   - Faut-il ensuite ajouter « données hébergées en Europe » sur /ia ?
2. **nginx** : `client_max_body_size` doit être d'au moins 9 Mo sur l'API pour les photos. La config n'est pas dans le dépôt.
3. **Photos d'exemple** par métier sur /ia (2 par métier, libres de droits) : à fournir.
4. **HEIC** : faut-il un décodeur serveur (`pillow-heif`) pour les navigateurs hors Safari ?
5. **Vignettes du dashboard** : l'image entière suffit-elle, ou faut-il stocker une miniature ?
6. **Renommer** le module « Réceptionniste IA » dans le sélecteur ?
7. **Extras R11** non faits : encart « ce qu'elle aurait capté chez vous ce mois-ci », scénario de la vidéo de prospection.
8. **Remboursement** « premier mois satisfait ou remboursé » : manuel, ça convient ?
9. **Relances à 79 €** : un prospect qui a reçu un email à 29 € voit 79 € dans les relances, sur la démo et au paiement. Ça convient ?
10. **Scoring prospect** : brancher les événements de /ia et les demandes de l'assistant dans `behavior_service` ?
11. **Résiliation** : à l'annulation d'un abonnement, l'assistant reste `delivered`. Le widget répond toujours et les alertes R10 partent encore ; le rapport, lui, s'arrête. Que doit-il se passer à la résiliation ?
12. **Page publique pour les clients** : faut-il une page publique de l'assistant vendu, sans texte de vente, à mettre sur la fiche Google ? Aujourd'hui, /ia est la page de vente.
13. **Adresse d'embed** : `custom_domain` n'est modifiable nulle part. Le rapport se rabat sur le site du prospect. Faut-il un champ dans Personnaliser ?
14. **Portail Stripe** : l'enregistrer une fois dans Stripe (Settings → Billing → Customer portal : factures, carte, résiliation immédiate ou en fin de période). Sans cette configuration, le bouton de l'espace client affiche « indisponible ».
15. **Lien de l'espace client** : pas de révocation individuelle (un lien fuité reste valable jusqu'à son expiration, 30 jours). Faut-il un bouton « révoquer les liens » (une version par assistant dans la signature) ?
16. **Standards du demo-host** : l'espace client y vit (demande du prompt) avec des appels publics par lien signé. À acter comme exception à la règle « pas d'appels API authentifiés / privés ».

## Petits points laissés en l'état

- L'email de résumé R3 dit toujours « votre réceptionniste virtuelle », même pour un prénom masculin. Le rapport R9 accorde déjà via `resolve_persona_gender` ; il suffit d'en faire autant dans `request_email.py`.
- `api/.env.example` (ligne existante, non modifiée) propose `GROQ_MODEL=llama-3.3-70b-versatile`, un modèle retiré le 2026-06-17 selon `core/config.py`. Il faut le supprimer ou le remplacer par `openai/gpt-oss-120b`.
- `HTTP_413_REQUEST_ENTITY_TOO_LARGE` (route photo) est déprécié à partir de Starlette 0.48 (simple avertissement). Tout le code l'utilise encore ; le remplacer partout d'un coup.
- Le journal des conversations n'affiche pas la marque « test ».

## Non commencés

- **R2** — prise de rendez-vous : OAuth Google Calendar, créneaux, confirmation et rappel SMS.
- **R1** — base de connaissance complète : documents, re-crawl, sources, navigation du site.

Ces tickets demandent chacun une vraie session (OAuth, ingestion de documents).
