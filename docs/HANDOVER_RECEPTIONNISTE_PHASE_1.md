# Passation — Réceptionniste IA, phase 1 (modèle économique)

Branche **`feat/receptionist-phase-1`** : un commit par ticket (R2 en deux, R11 en deux), plus ceux de ce
document (14 commits), posés sur `main` à `a0e6205`. `origin/main` n'a pas bougé depuis : la
branche passe en avance rapide, sans conflit. Rien n'est mergé, `main` n'a pas été poussé.

| Ticket | Asana | Commit | État |
|---|---|---|---|
| R3 — demandes structurées + email de résumé + boîte de réception | 1218810013765436 | `3caa9c2` | livré |
| R10 — alertes au commerçant (SMS / email, nuit, rappel J+1, signal 48 h) | 1218810158812114 | `f2908bc` | livré |
| R6 — devis par photo | 1218810139834916 | `1d62798` | livré |
| R4 — Mistral d'abord, secours Groq journalisé, « EU only » | 1218810158843341 | `0a65ac3` | livré ; en attente de la clé Mistral et des CGU |
| R11 — 79 €, 5 emails + 5 SMS de prospection, textes de /ia | 1218810139755803 | `e46cf0a` | livré (périmètre prix / modèles / page) |
| R9 — rapport mensuel au client + drapeau churn | 1218810013839351 | `d38c6fa` | livré (le rapport est aussi dans l'espace client, R8) |
| R8 — espace client par lien magique | 1218821404873061 | `2fafebd` | livré |
| R2 — rendez-vous : demande de créneaux sans agenda (R2a) | 1218810064722315 | `ff96da8` | livré |
| R2 — rendez-vous : Google Agenda (R2b) | 1218810064722315 | `94e9c1b` | livré ; en attente de la vérification Google (R15) |
| R1 — base de connaissance complète | 1218810139188474 | `48a5451` | livré ; à vérifier avec un vrai modèle |
| R13 — argumentaire face à IONOS | 1218810139800577 | `e19889c` | écrit : `docs/RECEPTIONNISTE_ARGUMENTAIRE.md` |
| R11 (suite) — encart d'estimation sur /ia | 1218810139755803 | `ac30c5a` | livré ; volumes par métier à valider |

Chaque ticket a reçu sur Asana un commentaire « fait / reste / comment tester ». La documentation
fonctionnelle à jour est dans `docs/ASSISTANT_MODULE.md` (sections Journal des conversations, Demandes,
Modèles IA, Devis par photo, Alertes au commerçant, Rapport mensuel, Espace client, Rendez-vous dans Google
Agenda, Sources de connaissance, Vente par abonnement).

Hors de cette branche : R12 (verticales, détection « déjà équipé », score « demande entrante ») est sur
`claude/epic-bohr-lgv8d8`, 5 commits au 24/09 au soir (dont un correctif d'horodatage `243c838`), lui non plus
pas mergé.

## Rejouer

```bash
cd api
python migrations/run_migrations.py      # idempotent ; les 13 migrations de la phase 1 sont listées plus bas
python -m pytest -q                      # attendu : 1120 passed, 3 failed (préexistants, voir plus bas)
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
11. `add_ai_assistant_request_appointment_slots` (R2a) : colonne `ai_assistant_requests.appointment_slots_json`.
12. `add_ai_assistant_calendars_tables` (R2b) : tables `ai_assistant_calendars` et `ai_assistant_appointments`.
13. `add_ai_assistant_documents_table` (R1) : table `ai_assistant_documents`.

Tests par ticket (depuis `api/`, avec `python -m pytest -q`) :

| Ticket | Fichiers | Tests |
|---|---|---|
| R3 | `tests/test_assistant_requests.py tests/test_assistant_opening_hours.py tests/test_assistant_request_analysis.py tests/test_ai_assistant_service.py` | 17 + 16 + 11 + 8 |
| R10 | `tests/test_assistant_request_alerts.py` | 18 |
| R6 | `tests/test_assistant_photos.py` | 15 |
| R4 | `tests/test_assistant_llm_router.py tests/test_ai_assistant_chat.py` | 15 + 6 |
| R11 | `tests/test_assistant_sales_copy.py tests/test_sms_templates.py tests/test_assistant_pricing.py` | 8 + 23 + 5 |
| R9 | `tests/test_assistant_reports.py tests/test_ai_assistant_conversations.py` | 26 + 5 |
| R8 | `tests/test_assistant_client_space.py` | 14 |
| R2a | `tests/test_assistant_appointments.py` | 16 |
| R2b | `tests/test_assistant_calendar.py` | 41 |
| R1 | `tests/test_assistant_documents.py tests/test_ai_assistant_website_knowledge.py` | 28 + 6 |
| R11 (suite) | `tests/test_assistant_opening_hours.py tests/test_assistant_sales_copy.py` (tests d'estimation) | 2 + 13 |

Échecs et erreurs **préexistants**, identiques sur `main` à `a0e6205` (revérifié sur un worktree de
`main`) :

- `tests/test_sms_auto_planning.py::test_slots_already_planned_keep_their_capacity_reserved` dépend de la date du jour.
- `tests/test_storyblok_space_swap.py::test_swap_needed_when_trial_would_end_before_demo_ttl` et `::test_boundary_exactly_enough_trial_remaining`.
- Typecheck `web` : 5 erreurs, `demo-host` : 2 erreurs. Ce sont des chemins Windows absolus (`C:/Users/…`) dans les types générés, plus un type PostHog. Aucune nouvelle erreur.

Environnement de ce poste : pas de clés Mistral / Groq / smsmode / Resend / Google. Tout ce qui touche un
service externe est testé avec des doublures. Les écrans de R3 à R9 ont été relus dans le code. Ceux de R8, R2,
R1 et de l'encart /ia ont été vérifiés dans Chromium, avec une API locale sur SQLite et des services simulés.

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

**À faire pour mettre R4 en service** (rien à coder) :

1. **Conditions Mistral** : relire et accepter les CGU et le DPA de La Plateforme (région UE, durée de conservation,
   pas d'entraînement sur les données envoyées).
2. **Clé** : créer `MISTRAL_API_KEY` sur console.mistral.ai et l'ajouter à l'environnement de l'API en prod. Les
   modèles (`MISTRAL_CHAT_MODEL`, `MISTRAL_VISION_MODEL`, `mistral-small-latest` par défaut) et les prix
   (`MISTRAL_EUR_PER_MTOK_IN` / `_OUT`, 0,10 / 0,30 € par million de tokens par défaut) ne changent que si le tarif
   diffère.
3. **Contrôle** : redémarrer l'API, poser une question à une démo `?internal=1`, et chercher dans les logs une ligne
   `assistant_llm_call usage=chat provider=mistral`.
4. **Bench** : `cd api && python scripts/bench_assistant_llm.py --out bench.md` (les 3 assistants en ligne les plus
   récents, ou des slugs). Objectif : 0,02 € au plus par conversation et aucune réponse qui cite un prix. Relire
   `bench.md`. Le refaire sur un assistant avec son site et 2 PDF (R1 : prompt d'environ 8 000 tokens).
5. **EU only** : la case de « Personnaliser » n'est acceptée qu'une fois la clé en place. La cocher pour les clients
   qui le demandent (sans secours Groq, une panne Mistral laisse le visiteur sur la réponse de secours).
6. **Mention « Europe » sur /ia** : seulement après les points 1 à 4 (question 1).

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

**Non vérifié** : aperçus de campagne dans un navigateur (la page /ia a été vérifiée avec son encart, voir « R11 (suite) »).

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

## R2a — Rendez-vous sans agenda : les créneaux souhaités

**Fichiers**
- API :
  - `services/ai_assistant/appointment_slots.py` : `AiAssistantAppointmentSlots` (offre, contrôle, libellés « lun. 28/09, matin »), `enums/ai_assistant_request.py` (`AiAssistantDayPeriod`)
  - `models/ai_assistant_request.py` (`appointment_slots_json`) + `migrations/add_ai_assistant_request_appointment_slots.py`
  - `request_service.capture` (contrôle, enregistrement, type rendez-vous dès la capture) et `follow_up` (type rendez-vous gardé, sauf urgence)
  - `request_email.py` (bloc « Créneaux souhaités (à confirmer) »), `request_alerts.py` (`AlertSms` : créneaux juste après le contact, jamais coupés)
  - route publique `GET /ai-assistants/public/{slug}/appointment-slots` ; champ `slots` de `POST …/lead` (422 si un créneau n'est plus proposé) ; `appointment_slots` dans les demandes du dashboard et de l'espace client
- Widget : `AssistantChat.vue` (chip « 📅 Prendre rendez-vous », bouton calendrier, panneau des créneaux, textes en 5 langues), `types/AiAssistant.ts`.
- Demo-host : `ClientSpaceRequests.vue` affiche les créneaux.
- Web : créneaux sous le résumé dans la liste des demandes.

**Vérifié**
- Tests (16) : offre suivant les horaires (demi-journées ouvertes, jours fermés, à partir de demain, 6 jours) ; horaires inconnus = lundi-vendredi ; commerce fermé toute la semaine = rien ; contrôle (2 au plus, dédoublonnés, triés ; refus d'un créneau non proposé, du jour même, d'un jour fermé ou trop loin) ; libellés ; capture (enregistrée, refusée sans rien enregistrer, la même visite garde ses créneaux ou en ajoute) ; suivi (rendez-vous malgré le modèle, urgence gardée, email avec le bloc, SMS d'un segment avec le créneau) ; SMS avec le vrai lien, un long résumé et un nom long (les deux créneaux restent entiers), contact de 60 caractères (un seul créneau, ou aucun) ; routes publiques (offre, 404, 422) ; charge utile (3 créneaux ou période inconnue refusés) ; migration rejouable.
- Navigateur (Chromium, API locale sur SQLite + `nuxt dev`) : parcours complet dans l'iframe de 440 × 680 et sur mobile 390 × 844 (5 langues offertes, le pire cas), un 3ᵉ choix remplace le plus ancien, confirmation au visiteur, parcours en allemand, demande affichée avec ses créneaux dans l'espace client. Pas de débordement horizontal, pas d'erreur console.

**Non vérifié** : email et SMS réels.

**Décisions prises seul**
- Pas de réservation : le visiteur choisit 1 ou 2 demi-journées (matin, après-midi), le commerce rappelle pour confirmer. 6 jours proposés, à partir de demain, sur 3 semaines au plus.
- Une demi-journée est ouverte si le commerce l'est à l'une des heures sondées (8 h 30 → 11 h 30, 13 h 30 → 17 h 30, heure de Paris). Jour sans horaire lisible : du lundi au vendredi.
- Un 3ᵉ choix remplace le plus ancien, sans message d'erreur.
- Une demande avec créneaux est un rendez-vous, sauf si l'analyse ou une photo y lit une urgence.
- SMS : les créneaux passent avant le résumé et le lien de l'espace client (jamais coupés) ; faute de place, le nom est raccourci, puis seul le premier créneau reste.
- Un 422 n'est lu comme « créneau retiré » que s'il porte une phrase (un champ refusé en porte une liste) ; les champs du formulaire ont la longueur maximale de l'API.
- Le serveur revérifie les créneaux à l'envoi : minuit passé, un créneau du lendemain devient « du jour » et n'est plus proposé (422, le widget recharge l'offre).
- Pendant le choix et le formulaire, les suggestions et « Être rappelé » s'effacent pour que tout tienne dans 440 × 680 (le formulaire « Être rappelé » débordait déjà avec 5 langues).

---

## R2b — Rendez-vous dans Google Agenda

**Fichiers**
- API :
  - `services/ai_assistant/google_calendar_client.py` : consentement, échange et rafraîchissement des jetons, adresse du compte, freeBusy, création d'événement (identifiant fixé par nous), révocation
  - `services/ai_assistant/calendar_service.py` : `state` OAuth signé, connexion, réglages, offre (premier créneau libre par demi-journée), réservation sous verrou, repli sur la demi-journée, libellés « réservé »
  - `services/ai_assistant/appointment_notices.py` : textes du visiteur en 4 langues, fichier `.ics`, confirmation, rappel J-1, passe de la boucle
  - `models/ai_assistant_calendar.py`, `models/ai_assistant_appointment.py`, `enums/assistant_calendar_status.py`, `enums/assistant_booking_mode.py`, `migrations/add_ai_assistant_calendars_tables.py`
  - routes : offre publique en mode agenda (`after`), `booking` de `POST …/lead` (409 si pris), `offer_booking` du chat ; espace client `calendar/connect`, `PATCH`/`DELETE calendar`, retour Google `calendar/google/callback`
  - `request_alerts.py` (SMS « RDV réservé le … par … »), `request_email.py` (bloc « Dans votre agenda »), `request_service.follow_up` (reste un rendez-vous), `request_runner.py` (passe des messages au visiteur), `chat_service.asks_for_appointment`, règle du prompt (`knowledge_builder.py`), `client_space_email.render_calendar_connected`, `opening_hours.business_timezone`
  - `core/config.py` et `.env.example` : `GOOGLE_CALENDAR_REDIRECT_URI`
- Widget : mode agenda du panneau (types, 3 créneaux, « Autres créneaux », réservation, 409), ouverture par le chat, `types/AiAssistant.ts`.
- Demo-host : `components/ClientSpaceCalendar.vue` (Connexions), `ClientSpaceAppointments.vue` (prochains rendez-vous), `utils/ContactLinkUtils.ts` (partagé avec `ClientSpaceRequests.vue`), page `client/[token].vue`.
- Web : « Rendez-vous réservé dans l'agenda du client » dans la liste des demandes.

**Vérifié**
- Tests (41, Google simulé) : `state` (expiration, falsification) ; client HTTP par `httpx.MockTransport` (URL de consentement, jetons et permissions, freeBusy en UTC, événement à l'heure de Paris, identifiant d'agenda encodé, 401 / `invalid_grant` / permissions manquantes = reconnexion, limite de débit non, 409 = déjà créé) ; connexion (jetons chiffrés, démo refusée, permission décochée = rien d'enregistré) ; rafraîchissement du jeton ; offre (premier créneau par demi-journée, délai, pause de midi, fermeture, week-end, horaires inconnus, pages, rendez-vous déjà réservés) ; réservation (événement, rappel, grille, type obligatoire, créneau pris, une réservation par demande, deux visiteurs sur le même créneau, relance après une réponse perdue avec le même identifiant, cache vidé après un créneau pris, refus en lecture seule gardé comme dernier problème, plafond de 20 par jour) ; SMS réservés aux mobiles des pays servis ; identifiant d'agenda vérifié (rien n'est changé s'il est illisible) ; reconnexion d'un autre compte ; rappel J-1 seulement la veille entre 9 h et 20 h, abandonné le jour même, email « Rappel » ; canal de confirmation renvoyé au widget ; repli et agenda « à reconnecter » ; canaux du visiteur ; SMS d'un segment dans les 4 langues ; email et `.ics` ; réservation unique des messages ; rappels dus, trop tardifs ; confirmation perdue reprise ; routes publiques (offre, repli, réservation, 409) ; intention de rendez-vous du chat (FR, NL, DE, EN, « terminé » ignoré) ; espace client (états, rendez-vous à venir, connexion, réglages, 422, déconnexion et révocation, page de retour) ; alertes au commerçant ; migration rejouable.
- Navigateur (Chromium, API locale sur SQLite avec un faux Google + `nuxt dev`) : réservation complète dans l'iframe de 440 × 680 et sur mobile (types, pages, confirmation) ; créneau pris par un autre visiteur (message, nouvelle offre) ; ouverture du panneau par une question au chat ; espace client connecté (demande « réservée », prochains rendez-vous, réglages enregistrés) et non connecté (l'onglet part bien vers `accounts.google.com`, que le bac à sable ne laisse pas charger).

**Non vérifié** : vrai Google (pas de client OAuth ici), SMS et email réels au visiteur, rendu de l'email dans Gmail.

**Décisions prises seul**
- Permissions : `calendar.events` ne suffit pas à lire les disponibilités ; `calendar.freebusy` est demandé en plus (le plus étroit des accès acceptés par freeBusy).
- Pas de choix de l'agenda dans une liste (il faudrait l'accès `calendar.calendarlist.readonly`) : `primary` par défaut, ou l'identifiant collé par le client.
- Retour de Google dans un nouvel onglet, sur une page de l'API qui ne porte aucun lien de l'espace client ; la page d'origine se recharge quand on y revient.
- Aucune révocation chez Google, ni à la reconnexion ni à la déconnexion : révoquer un jeton révoque toute l'autorisation du compte (les nouveaux jetons, un autre assistant, les connexions Google de l'opérateur s'il teste avec son compte). La déconnexion efface les jetons ici et explique comment retirer l'accès côté Google.
- Pas de verrou de base pendant les appels à Google : la session SQLAlchemy est synchrone dans des routes asynchrones et l'API tourne sur un seul worker ; une attente de verrou bloquerait toute l'API. Verrou en mémoire par agenda, événement créé avant la ligne, transactions courtes.
- Garde-fous contre l'envoi de SMS à n'importe qui depuis le widget public : 20 réservations au plus par assistant et par 24 h, SMS seulement vers un mobile FR / BE / LU / CH / DE, en plus de la limite de 8 demandes par 5 min et par IP.
- Offre : le premier créneau libre de chaque demi-journée, trois par page, pour proposer des moments différents plutôt que trois créneaux collés.
- Défauts : 1 h, 24 h de délai minimum ; créneaux de 6 h à 21 h 30 dans les horaires ; lundi-vendredi 9 h-12 h et 14 h-18 h quand les horaires sont inconnus.
- Une demande n'a qu'un rendez-vous ; le visiteur qui veut le déplacer appelle le commerce (pas d'annulation en ligne).
- Le `state` OAuth n'est pas lié au navigateur qui l'a demandé (valable 15 min) : un lien de consentement qui fuiterait permettrait à un autre compte Google de s'attacher ; l'email d'avis envoyé au commerçant à chaque connexion le signale.
- La demande reste « à traiter » après une réservation : le commerçant la marque traitée comme les autres.
- Le visiteur est prévenu par le canal qu'il a laissé : SMS pour un mobile, email (avec `.ics`) pour une adresse ; rappel J-1 par email quand il n'a pas laissé de mobile.
- Une visite `?internal=1` réserve pour de vrai, avec un événement « [Test] … » : c'est ce qui permet le test d'acceptation (événement dans l'agenda de test, SMS reçu).

## R1 — Base de connaissance complète

**Fichiers**
- API :
  - `services/ai_assistant/document_text.py` : texte d'un PDF (`pypdf==6.19.0`, ajouté à `requirements.txt`) lu dans un processus à part (`python -m services.ai_assistant.document_text`), un à la fois, arrêté au bout de 30 s ; nettoyage, borne, refus motivés (scan, mot de passe, illisible, trop lourd, trop long à lire)
  - `services/ai_assistant/document_service.py` : ajout (lecture, fichier dans R2, ligne, recopie dans la connaissance ; pas de fichier orphelin si l'écriture échoue), activation, suppression
  - `services/ai_assistant/source_service.py` : interrupteurs site / fiche, relecture du site (bouton et boucle hebdomadaire) ; `website_sync.py` : écarts entre deux lectures, lecture incomplète mise de côté
  - `services/ai_assistant/knowledge_budget.py` : budget du prompt (tout entier si ça tient, sinon les passages les plus proches des 3 derniers messages du visiteur, chaque source gardant son début)
  - `knowledge_builder.py` : pages et documents encadrés comme données, liens, citation des documents, interrupteurs ; `chat_service.py` : messages du visiteur transmis, taille du prompt journalisée ; `scripts/bench_assistant_llm.py` : même prompt que le chat
  - `assistant_service.py` : la régénération garde documents et interrupteurs, note la lecture du site, garde les pages d'un site injoignable ; `get_for_owner` (aussi utilisé par `_owned_assistant_or_404`)
  - `models/ai_assistant_document.py` (table en utf8mb4), `enums/assistant_knowledge_source.py`, `migrations/add_ai_assistant_documents_table.py`, `schemas/ai_assistant_sources.py`, routes `api/v1/routes/ai_assistant_sources.py`
  - `r2_storage_service.py` (`documents/assistant/…`), stockage admin (type « document d'assistant »), `main.py` (boucle, journal INFO du chat)
- Web : `components/ui/AssistantSourcesDrawer.vue` (volet « Sources »), bouton « Sources » de la carte, `services/aiAssistantService.ts`, `types/AiAssistantSources.ts`, pile de volets.
- Widget : `utils/MessageLinkUtils.ts` (liens des réponses, sans les `**` du Markdown).

**Vérifié**
- Tests (28 + 6) :
  - PDF construits en mémoire : texte page après page, césures (pas les nombres ni les noms propres), borne à un saut de ligne, refus (scan, mot de passe, lourd, pas un PDF), page d'illustration ignorée ;
  - lecture dans un processus à part : texte rendu, refus transmis, arrêt au délai, un PDF à la fois ;
  - budget : tout entier quand ça tient, sinon les passages proches de la question dans l'ordre de lecture ; une relance sans mot en commun garde le début de chaque page et de chaque document ;
  - documents : lus, stockés, recopiés tant qu'activés, bornés à 10 (même quand un autre envoi arrive pendant la lecture), propres à leur assistant, pas de fichier orphelin si le stockage ou l'écriture échoue ; table en utf8mb4 ;
  - site : écarts d'une relecture, pages gardées quand le site tombe ou que la lecture de la semaine en perd plus de la moitié (« Mettre à jour » la prend), seuls les assistants vendus lus il y a 7 jours sont dus, document ajouté pendant une relecture gardé, site jamais lu proposé à la lecture ;
  - régénération : interrupteurs et documents gardés, pages d'un site injoignable gardées, écarts notés, site mort plus lu ;
  - prompt : encadrement `<<< >>>` (une page ne peut pas fermer son bloc), lien et citation, fiche puis site puis documents, fiche ou site coupés, document désactivé absent, passages « (extraits) » et « […] », 3 derniers messages transmis, taille journalisée ;
  - routes : propriétaire seulement (404 sinon), taille vérifiée avant lecture (413), PDF refusé expliqué (422).
- À la main : un PDF de 11 Ko dont les 60 pages partagent un flux de texte de 900 Ko (des minutes de lecture) est arrêté à 30 s ; l'API a continué de répondre pendant ce temps (298 battements de 100 ms sur 300) et aucun processus de lecture n'est resté. Deux PDF de 9 et 15 Ko qui gonflent en 0,9 et 4 Mo d'instructions de dessin par page sont refusés en 0,2 s.
- Navigateur (Chromium, API locale sur SQLite + `nuxt dev`) :
  - volet « Sources » sur bureau et mobile : pages et tailles, fiche, « Mettre à jour » (« 2 pages modifiées (1 ajoutée, 1 changée) »), dépôt d'un PDF, interrupteurs ;
  - lien cliquable dans une réponse du widget (440 × 680).

**Non vérifié** : réponses d'un vrai modèle sur un site et deux PDF (pas de clé Mistral / Groq ici) ; relecture d'un vrai site ; dépôt vers le vrai R2 ; création de la table sur le vrai MySQL.

**Décisions prises seul**
- « selon votre site » disparaît du prompt : il s'adressait au visiteur comme s'il était le commerçant. L'assistante donne l'adresse de la page (« Voir nos tarifs : https://… ») ou nomme le document.
- Le site préparé par DevLeadHunter est rangé avec la fiche Google (il en est tiré) : couper la fiche le coupe aussi. Fiche coupée : téléphone, adresse, description, note, horaires, services et avis disparaissent ; le nom du commerce reste et les horaires viennent du site ou des documents s'ils les donnent.
- Budget : 24 000 caractères pour le site et les documents (environ 6 000 tokens, un prompt d'environ 8 000 tokens). Découpage en passages seulement au-delà, classés par mots en commun avec les 3 derniers messages du visiteur, sans embeddings. Aux prix par défaut (0,10 € le million de tokens d'entrée), 6 messages à 8 000 tokens coûtent environ 0,005 €.
- Documents : PDF avec du texte seulement (pas d'OCR des scans), 10 par assistant, 10 Mo, 60 pages, 30 000 caractères. Plusieurs fichiers du même nom sont acceptés.
- Lecture des PDF dans un processus Python à part plutôt qu'un fil : un fil ne s'arrête pas, et un PDF piégé aurait occupé l'unique worker de l'API. Un seul PDF à la fois ; le second reçoit « Un autre PDF est en cours de lecture ».
- Relecture hebdomadaire réservée aux assistants vendus (une démo se relit à la régénération) ; 10 assistants au plus par passage horaire, l'un après l'autre. Une relecture qui perd plus de la moitié des pages ou du texte est mise de côté ; le bouton, lui, prend toute lecture.
- Le volet « Sources » est dans le dashboard (opérateur), pas dans l'espace client.
- Chaque écriture de la connaissance qui suit une attente (lecture du site, d'un PDF, régénération) relit d'abord l'assistant, pour ne pas écraser un changement fait entre-temps.

## R11 (suite) — Encart d'estimation sur /ia

**Fichiers**
- API : `services/ai_assistant/opening_hours.py` (`closed_hours_estimate`), `services/ai_assistant/request_volume.py` (volumes par métier), `schemas/ai_assistant.py` (`AiAssistantClosedHours`), route publique (`closed_hours`, démos seulement), `knowledge_builder.py` (jours de semaine fériée marqués `holiday`).
- Demo-host : `pages/ia/[slug].vue` (encart), `types/AiAssistant.ts`.

**Vérifié**
- Tests :
  - heures fermées de 7 h à 22 h sur une semaine et sur un mois : nuit du vendredi, horaires de nuit 20 h – 8 h, jour fermé, jour ouvert 24 h/24, jour sans horaires ;
  - semaine de jour férié mise de côté ;
  - estimation servie aux démos seulement, jamais pour une fiche fermée tous les jours ;
  - base par défaut sans prospect ;
  - arrondi au plus proche (12,5 → 13) ;
  - métier trouvé par début de mot (« Restaurant barbecue » n'est pas un barbier, « Installateur de portes de garage » n'est pas un garage, « Institut de formation » n'est pas un institut de beauté).
- Relecture de code (agent) : aucun point bloquant ; les 3 points importants (métiers mal reconnus, semaine de jour férié, hypothèse présentée comme un fait) et les 4 mineurs (« ≈ 1 demandes », arrondi, coût du calcul, contraste du chiffre) sont corrigés.
- Navigateur : /ia d'une démo de plombier ouverte 43 h par semaine affiche « ≈ 18 demandes » et le calcul, sur bureau et mobile ; rien sur un assistant vendu.

**Décisions prises seul**
- Le chiffre est une estimation affichée comme telle, calcul compris : un volume mensuel pour le métier, présenté comme « notre hypothèse », × la part du temps fermé entre 7 h et 22 h (horaires Google). Libellé « chaque mois » plutôt que « ce mois-ci » : le volume est mensuel, seules les heures fermées sont celles du mois en cours.
- Volumes retenus, des hypothèses à valider : plombier, serrurier, garage 30 ; électricien 20 ; couvreur, menuisier, peintre, bâtiment 15 ; coiffure, restaurant, cabinet de santé 40 ; institut de beauté 35 ; agence immobilière 25 ; autre 20.
- Plage « quand vos clients cherchent » : 7 h – 22 h, tous les jours.
- Encart masqué quand un jour n'a pas d'horaires lisibles, sur une semaine de jour férié, pour une fiche fermée tous les jours, et sous 2 demandes. Les assistants déjà créés n'ont la marque des jours fériés qu'après une régénération.
- Le chiffre est écrit à l'encre, pas dans la couleur du commerce, pour rester lisible quelle que soit sa couleur.

---

## Consolidation avant relecture

Aucune fonctionnalité nouvelle : une passe par commit (ou par écran pour l'interface), sur la même branche.

- **Surfaces publiques** (`fix: harden the receptionist public endpoints`) :
  - Changé :
    - chat public borné : 100 messages de 4 000 caractères au plus, rôles `user` / `assistant` seulement. Le widget envoie ses 40 derniers messages et limite la saisie à 2 000 caractères ;
    - lien « marquer traitée » limité à 30 ouvertures par 5 min et par adresse ;
    - un refus interne à la prise de rendez-vous ou de demande ne montre plus son texte au visiteur : phrase générique, détail dans le log ;
    - photos décodées en JPEG, PNG ou WEBP seulement, jamais par les lecteurs rares de Pillow ;
    - langues de l'espace client bornées ;
    - tests d'isolement : signature d'un lien « marquer traitée » réutilisée sur une autre demande, photo envoyée à un autre assistant, lien client qui ne touche que son propre agenda.
  - Vu et laissé :
    - la config publique n'a pas de limite de débit. Le rendu serveur du demo-host la lit depuis ses propres adresses : une limite par adresse bloquerait tous les visiteurs.
    - le `state` OAuth Google n'est pas lié au navigateur. Un client pourrait brancher l'agenda d'un tiers sur son propre assistant, à condition que ce tiers accepte l'écran de consentement Google. Risque jugé faible.
    - les liens client ne sont pas révocables (question 15).
    - le lecteur de site suit les redirections sans écarter les adresses internes. C'est déjà le cas sur `main` et ce n'est pas dans le périmètre de la branche.

## Questions pour Léo

1. **Mistral** :
   - Valider les CGU / DPA (région, rétention, pas d'entraînement), créer `MISTRAL_API_KEY`, puis lancer `python scripts/bench_assistant_llm.py` en prod (objectif ≤ 0,02 € par conversation).
   - Faut-il ensuite ajouter « données hébergées en Europe » sur /ia ?
2. **nginx** : `client_max_body_size` doit être d'au moins 9 Mo sur l'API pour les photos. La config n'est pas dans le dépôt.
3. **Photos d'exemple** par métier sur /ia (2 par métier, libres de droits) : à fournir.
4. **HEIC** : faut-il un décodeur serveur (`pillow-heif`) pour les navigateurs hors Safari ?
5. **Vignettes du dashboard** : l'image entière suffit-elle, ou faut-il stocker une miniature ?
6. **Renommer** le module « Réceptionniste IA » dans le sélecteur ?
7. **Extras R11** : l'encart d'estimation est fait (valider les volumes par métier, voir « R11 (suite) ») ; le scénario de la vidéo de prospection reste à faire.
8. **Remboursement** « premier mois satisfait ou remboursé » : manuel, ça convient ?
9. **Relances à 79 €** : un prospect qui a reçu un email à 29 € voit 79 € dans les relances, sur la démo et au paiement. Ça convient ?
10. **Scoring prospect** : brancher les événements de /ia et les demandes de l'assistant dans `behavior_service` ?
11. **Résiliation** : à l'annulation d'un abonnement, l'assistant reste `delivered`. Le widget répond toujours et les alertes R10 partent encore ; le rapport, lui, s'arrête. Que doit-il se passer à la résiliation ?
12. **Page publique pour les clients** : faut-il une page publique de l'assistant vendu, sans texte de vente, à mettre sur la fiche Google ? Aujourd'hui, /ia est la page de vente.
13. **Adresse d'embed** : `custom_domain` n'est modifiable nulle part. Le rapport se rabat sur le site du prospect. Faut-il un champ dans Personnaliser ?
14. **Portail Stripe** : l'enregistrer une fois dans Stripe (Settings → Billing → Customer portal : factures, carte, résiliation immédiate ou en fin de période). Sans cette configuration, le bouton de l'espace client affiche « indisponible ».
15. **Lien de l'espace client** : pas de révocation individuelle (un lien fuité reste valable jusqu'à son expiration, 30 jours). Faut-il un bouton « révoquer les liens » (une version par assistant dans la signature) ?
16. **Standards du demo-host** : l'espace client y vit (demande du prompt) avec des appels publics par lien signé. À acter comme exception à la règle « pas d'appels API authentifiés / privés ».
17. **Créneaux sans agenda** : faut-il proposer le jour même (l'après-midi, le matin) ? Aujourd'hui l'offre commence le lendemain.
18. **Google Agenda (R15)** :
    - Déclarer `GOOGLE_CALENDAR_REDIRECT_URI` (`https://<api>/api/v1/ai-assistants/calendar/google/callback`) dans le client OAuth Google.
    - Ajouter les accès `calendar.events` et `calendar.freebusy` à l'écran de consentement, puis lancer la vérification de l'application.
    - Tant qu'elle est en mode « Test », seuls les comptes testeurs peuvent se connecter et les jetons expirent au bout de 7 jours : l'agenda passe alors « à reconnecter ».
19. **Expéditeur des SMS au visiteur** : ce sont les SMS de confirmation et de rappel. Ils partent avec le nom d'expéditeur de Paramètres → Relance SMS (ex. « Dibodev »), le nom du commerce étant en tête du texte. Faut-il un expéditeur au nom de chaque commerce (11 caractères, à déclarer chez smsmode) ?
20. **Déplacer ou annuler** : le visiteur appelle le commerce, qui modifie l'événement dans son agenda. Faut-il un lien d'annulation dans la confirmation ?
21. **Documents dans l'espace client** : faut-il laisser le commerçant déposer lui-même ses PDF (et couper ses sources) depuis son espace ? Aujourd'hui, seul l'opérateur le fait, depuis le dashboard.
22. **Documents d'un assistant supprimé** : le texte et le fichier R2 restent (comme ses demandes et ses rapports). Faut-il les purger ?
23. **Relecture des démos** : seules les démos régénérées relisent le site. Faut-il aussi relire chaque semaine les démos en cours ?
24. **Jeu de caractères des tables de la phase 1** : `ai_assistant_requests`, `_photos`, `_reports`, `_calendars`, `_appointments` sont créées par `create_all` avec le jeu de caractères par défaut de la base. `fix_utf8mb4_collation` l'a passé en utf8mb4 si l'accès `ALTER DATABASE` était permis (sinon il l'a écrit en avertissement). À vérifier en prod : `SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_COLLATION NOT LIKE 'utf8mb4%';`. Si des tables sortent, `python migrations/fix_utf8mb4_collation.py` (idempotent) les convertit. La table des documents est déjà déclarée en utf8mb4.

## Petits points laissés en l'état

- L'email de résumé R3 dit toujours « votre réceptionniste virtuelle », même pour un prénom masculin. Le rapport R9 accorde déjà via `resolve_persona_gender` ; il suffit d'en faire autant dans `request_email.py`.
- `api/.env.example` (ligne existante, non modifiée) propose `GROQ_MODEL=llama-3.3-70b-versatile`, un modèle retiré le 2026-06-17 selon `core/config.py`. Il faut le supprimer ou le remplacer par `openai/gpt-oss-120b`.
- `HTTP_413_REQUEST_ENTITY_TOO_LARGE` (route photo) est déprécié à partir de Starlette 0.48 (simple avertissement). Tout le code l'utilise encore ; le remplacer partout d'un coup.
- Le journal des conversations n'affiche pas la marque « test ».
- Créneaux ajoutés après l'annonce : un visiteur qui recharge la page et choisit des créneaux dans les 24 h met à jour sa demande déjà annoncée ; le commerçant les voit dans le dashboard et l'espace client, pas dans un nouvel email ni un nouveau SMS (seulement dans le rappel J+1).

