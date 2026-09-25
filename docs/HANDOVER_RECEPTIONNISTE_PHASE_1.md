# Passation — Réceptionniste IA, phase 1 (modèle économique)

Branche **`feat/receptionist-phase-1`** : un commit par ticket (R2 en deux, R11 en deux) et ceux de ce
document (14 commits), puis la consolidation avant relecture (38 commits, sans fonctionnalité nouvelle), soit 52
commits posés sur `main` à `a0e6205`. `origin/main` n'a pas bougé depuis (revérifié au 24/09 au soir) : la
branche passe en avance rapide, sans conflit. Rien n'est mergé, `main` n'a pas été poussé. La relecture du
25/09 a ajouté neuf commits de correction (voir « Relecture finale ») et préparé la fusion avec R12 sur
`release/receptionist-phase-1`.

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
| Consolidation 1 — surfaces publiques | — | `0fa29c6` | fait |
| Consolidation 2 — utf8mb4 sur les 8 tables, dates Stripe en UTC | — | `ec27c10` | fait |
| Consolidation 3 — relecture du diff : 6 `fix`, 18 `refactor` | — | `2ec40bb` → `95ae98e`, `9e2337a` | fait ; points 🟡 / ⚪ listés dans « Relecture : points laissés pour plus tard » |
| Consolidation 4 — interface, un commit par écran | — | `edd0596` → `02d5def`, `bc8cf5d`, `5d962ab` | fait |
| Consolidation 5 — documentation et parcours de test manuel | — | `da2e58f`, `f8b4820`, `2e363e5`, et ce document | fait ; parcours non joués (pas de clés ici) |

Chaque ticket a reçu sur Asana un commentaire « fait / reste / comment tester ». La documentation
fonctionnelle à jour est dans `docs/ASSISTANT_MODULE.md`, rangée dans l'ordre de vie du produit : génération,
connaissance, démo, vente, après-vente, alertes et rapports, espace client, puis une partie Référence. Les
parcours à jouer à la main sont dans « Parcours de test manuel », plus bas.

Hors de cette branche : R12 (verticales, détection « déjà équipé », score « demande entrante ») est sur
`claude/epic-bohr-lgv8d8`, 5 commits au 24/09 au soir (dont un correctif d'horodatage `243c838`), lui non plus
pas mergé.

## Rejouer

```bash
cd api
python migrations/run_migrations.py      # idempotent ; les 13 migrations de la phase 1 sont listées plus bas
python -m pytest -q                      # attendu : 1140 tests, 2 ou 3 échecs préexistants (voir plus bas)
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
| R3 | `tests/test_assistant_requests.py tests/test_assistant_opening_hours.py tests/test_assistant_request_analysis.py tests/test_ai_assistant_service.py` | 18 + 16 + 11 + 8 |
| R10 | `tests/test_assistant_request_alerts.py` | 18 |
| R6 | `tests/test_assistant_photos.py` | 18 |
| R4 | `tests/test_assistant_llm_router.py tests/test_ai_assistant_chat.py` | 15 + 7 |
| R11 | `tests/test_assistant_sales_copy.py tests/test_sms_templates.py tests/test_assistant_pricing.py` | 8 + 23 + 5 |
| R9 | `tests/test_assistant_reports.py tests/test_ai_assistant_conversations.py` | 27 + 5 |
| R8 | `tests/test_assistant_client_space.py` | 14 |
| R2a | `tests/test_assistant_appointments.py` | 17 |
| R2b | `tests/test_assistant_calendar.py` | 43 |
| R1 | `tests/test_assistant_documents.py tests/test_ai_assistant_website_knowledge.py` | 27 + 6 |
| R11 (suite) | `tests/test_assistant_opening_hours.py tests/test_assistant_sales_copy.py` (tests d'estimation) | 2 + 13 |
| Consolidation | `tests/test_assistant_tables.py tests/test_assistant_signed_links.py` (plus les tests ajoutés aux fichiers ci-dessus) | 8 + 1 |

Échecs et erreurs **préexistants**, identiques sur `main` à `a0e6205` (revérifié sur un worktree de
`main`) :

- `tests/test_sms_auto_planning.py::test_slots_already_planned_keep_their_capacity_reserved` dépend de la date du jour (il passait le 24/09 au soir : 1138 passed, 2 failed).
- `tests/test_storyblok_space_swap.py::test_swap_needed_when_trial_would_end_before_demo_ttl` et `::test_boundary_exactly_enough_trial_remaining`.
- Typecheck `web` : 5 erreurs, `demo-host` : 2 erreurs. Ce sont des chemins Windows absolus (`C:/Users/…`) dans les types générés, plus un type PostHog. Aucune nouvelle erreur.

Environnement de ce poste : pas de clés Mistral / Groq / smsmode / Resend / Google. Tout ce qui touche un
service externe est testé avec des doublures. Les écrans de R3 à R9 ont été relus dans le code. Ceux de R8, R2,
R1 et de l'encart /ia ont été vérifiés dans Chromium, avec une API locale sur SQLite et des services simulés.
La passe d'interface a revu dans Chromium, à 1280 et 375 px, en clair et en sombre, la page Assistants IA,
« Personnaliser », le volet Sources, le widget et /ia.

## Parcours de test manuel

À jouer sur un poste qui a les clés : cette session n'en a aucune, et aucun de ces parcours n'a été joué contre de vrais services. `…` dans une adresse d'API vaut `/api/v1/ai-assistants`.

**Avant de commencer**
- Un assistant de test, généré sur un prospect de test dont l'email et le téléphone sont les vôtres. Jamais un vrai prospect ni l'un des 5 prospects de la prod : un assistant livré écrit à l'adresse et au mobile du commerce.
- **Démo** (`active`) : toujours ouverte avec `?internal=1`. La demande porte alors la marque Test, n'est jamais annoncée, et rien ne part vers PostHog.
- **Livré** (`delivered`) : payer son « Lien mensuel » (ligne Abonnement de la carte) en mode test Stripe, carte 4242 4242 4242 4242, ou en local `UPDATE ai_assistants SET status = 'delivered' WHERE id = …;` (sans abonnement : ni rapport mensuel ni section Abonnement). Sans `?internal=1`, une visite sur un assistant livré est réelle : alertes, compteurs, rapport.
- Outils du navigateur ouverts sur l'onglet Réseau (filtre `ai-assistants`), journaux de l'API dans un terminal. En local, `DEV_EMAIL_REDIRECT` renvoie chaque email vers votre adresse.
- Services : `GROQ_API_KEY` ou `MISTRAL_API_KEY` (sans clé, l'assistante donne sa réponse de secours), R2 (photos, PDF), `SMSMODE_API_KEY` et un expéditeur (Paramètres → Relance SMS), une identité d'envoi (Paramètres → Configuration d'envoi).

### Sources et documents (R1)

- Prérequis : démo ou livré, clé de modèle, R2, un PDF avec du texte (pas un scan) de moins de 10 Mo.
- Page Assistants IA, bouton « Sources » de la carte : `GET …/{id}/sources`. Le volet montre Site web (pages lues, dernière lecture), Fiche Google et les documents.
- « Mettre à jour » : `POST …/{id}/sources/refresh`, puis « Lu le 24/09/2026 à 10:05 : aucun changement. » ou « … : 2 pages modifiées (1 ajoutée, 1 changée). ».
- « Ajouter un PDF » : `POST …/{id}/documents` (201), « Lecture du PDF… », puis le document dans la liste, activé. Un scan est refusé, « Ce PDF ne contient pas de texte lisible (document scanné ?) » (422) ; un fichier de plus de 10 Mo aussi (413).
- Interrupteurs du site, de la fiche ou d'un document : `PATCH …/{id}/sources` ou `PATCH …/{id}/documents/{doc_id}`. Suppression : confirmation, puis `DELETE …/{id}/documents/{doc_id}`.
- Sur `/ia/{slug}?internal=1`, une question dont la réponse n'est que dans le PDF : l'assistante répond et nomme le document (« d'après notre document … »). Document désactivé : elle ne sait plus répondre, dès le message suivant.
- Une question sur une page précise du site : la réponse finit par l'adresse de la page, en lien (nouvel onglet).

### Modèles : Mistral, secours Groq, IA hébergée en Europe (R4)

- Prérequis : démo, `MISTRAL_API_KEY` et `GROQ_API_KEY`.
- Sur `/ia/{slug}?internal=1`, poser une question : `POST …/public/{slug}/chat` (200, `reply`). Journal de l'API : `assistant_llm_call usage=chat provider=mistral … fallback=False eu_only=False`.
- Secours : remplacer `MISTRAL_API_KEY` par une fausse clé, redémarrer l'API, reposer la question. La réponse arrive quand même ; le journal dit `provider=groq … fallback=True` ; les admins reçoivent « Mistral indisponible : chat de l'assistant basculé sur Groq » (une fois par 30 min au plus).
- « Personnaliser » → « IA hébergée en Europe (Mistral) » → « Enregistrer » : `PATCH …/{id}` (200). Sans `MISTRAL_API_KEY` : 422 et le message « « IA hébergée en Europe » impossible : la clé Mistral n'est pas configurée sur le serveur ».
- Interrupteur allumé et fausse clé Mistral : aucun appel à Groq. L'assistante propose de laisser ses coordonnées et les admins reçoivent « … sans réponse pour les assistants « IA hébergée en Europe » ».
- Bench, depuis `api/` avec les deux clés : `python scripts/bench_assistant_llm.py <slug>`. Il affiche latence moyenne et p95, tokens, coût par réponse et par conversation, réponses citant un prix, et écrit les réponses dans un fichier Markdown.

### Page de démo : prix, textes et estimation (R11)

- Prérequis : démo dont la fiche Google donne des horaires pour les 7 jours.
- Paramètres → Facturation & paiement, bloc « Abonnement Assistant IA » : 79 € par mois par défaut.
- `/ia/{slug}?internal=1` : « Plus aucune demande sans réponse », les trois preuves, « 79 €/mois, installation comprise, sans engagement, premier mois satisfait ou remboursé. » (`GET …/public/{slug}` : `monthly_price_label`).
- Changer le prix dans Facturation, recharger /ia : le nouveau prix. Avec `?subscribed=1`, ou sur un assistant livré : plus de prix.
- Encart « Estimation · chez vous, chaque mois » : « ≈ N demandes » et le calcul (volume du métier × part du temps fermé entre 7 h et 22 h). Config publique : `closed_hours`. Absent sur un assistant livré, si un jour n'a pas d'horaires lisibles, ou sous 2 demandes.
- Modèles : page Modèles d'email (`/dashboard/email-templates`), les 5 « Assistant IA - … » ; volet d'une campagne, les 5 modèles SMS `assistant-*`. L'aperçu remplace `{lien_assistant}` et `{prix_assistant}` ; `GET /api/v1/sms/templates/{key}/preview` rend `segments: 1` pour chacun.

### Demandes (R3)

- Prérequis : démo (`?internal=1`). L'email de résumé au commerce se teste avec un assistant livré (parcours Alertes).
- `/ia/{slug}?internal=1` : poser une question, puis « Être rappelé » : nom, email ou téléphone, besoin, « Envoyer ».
- `POST …/public/{slug}/lead` : le corps porte `session_id` et `internal: true`, la réponse `ok: true`. Le widget répond « Merci, vos coordonnées sont transmises. On vous recontacte très vite. ».
- Assistants IA (rechargée), section Demandes, onglet « Toutes » : la demande, badge Test, typée et résumée en quelques secondes. Sans clé de modèle : type par mots-clés, résumé tiré des mots du visiteur. Elle n'est ni dans « À traiter » ni dans les KPI.
- Envoyée en dehors des horaires Google du commerce : pastille « Hors horaires ».
- Renvoyer le formulaire dans la même visite : la même demande est mise à jour, sans doublon.
- « Marquer traitée », « Sans suite », « Rouvrir » : `PATCH …/requests/{id}`, et le statut de la ligne suit.

### Devis par photo (R6)

- Prérequis : démo, R2, un modèle qui lit les images (Mistral, ou le modèle vision de Groq), une photo JPEG, PNG ou WEBP de moins de 8 Mo.
- `/ia/{slug}?internal=1` : puce « Envoyer une photo pour un devis », ou l'appareil photo de la barre de saisie. Le panneau affiche la mention (photo supprimée au bout de 90 jours, pas de personnes), puis « Choisir une photo ».
- `POST …/public/{slug}/photo` (multipart, 200 : `accepted`, `reply`, `need`, `remaining`). Le fil montre la vignette et « Photo envoyée », puis la réponse : ce qui est visible, 2 questions au plus, jamais de prix.
- Le formulaire de coordonnées s'ouvre ensuite avec le besoin pré-rempli. Envoyé : dans Assistants IA, onglet « Toutes », une demande « Devis » avec la vignette, ou « Urgence » si la photo montre un risque immédiat.
- Photo hors sujet (un paysage) : refus poli, et la photo est retirée de R2 (son lien public ne répond plus).
- Après 3 photos dans la visite, le bouton photo se grise (l'API refuserait une 4ᵉ en 409). Une photo HEIC depuis Chrome : « Je ne peux pas lire ce fichier … » (415).
- Sans modèle vision : la photo est gardée et la réponse reste neutre.

### Rendez-vous sans agenda : créneaux souhaités (R2a)

- Prérequis : démo, ou assistant livré sans agenda connecté.
- `/ia/{slug}?internal=1` : puce ou bouton « Prendre rendez-vous » : `GET …/public/{slug}/appointment-slots` (`mode: "request"`, 6 jours, `max_chosen: 2`).
- Le panneau montre les demi-journées ouvertes à partir de demain. En cocher 2 (une 3ᵉ remplace la plus ancienne), « Continuer », coordonnées, « Envoyer ».
- `POST …/public/{slug}/lead` avec `slots`. Le widget répond « Merci ! Votre demande de rendez-vous est transmise (…). On vous recontacte pour confirmer. ».
- Assistants IA : demande « Rendez-vous », avec « Créneaux souhaités (à confirmer) : mar. 29/09, matin ou jeu. 01/10, après-midi » sous le résumé.
- Sur un assistant livré, sans `?internal=1` : l'email de résumé a le bloc « Créneaux souhaités (à confirmer) » et le SMS « …, pour mar. 29/09 matin ou … : … ».
- Commerce sans horaires lisibles : du lundi au vendredi seulement.

### Alertes au commerçant (R10)

- Prérequis : assistant livré ; smsmode, expéditeur et identité d'envoi ; visite **sans** `?internal=1` (une visite interne n'est jamais annoncée).
- « Personnaliser » : « Mobile du commerçant » = votre mobile, SMS et « Email de résumé (toutes les demandes) » allumés, « SMS immédiat pour » : devis, rendez-vous, urgence (défaut).
- `/ia/{slug}` : demander un devis, puis « Être rappelé » avec votre téléphone. `POST …/public/{slug}/lead`, puis dans la minute :
  - email « Demande de devis — Nom » (« (hors horaires) » en dehors des horaires) à l'adresse du commerce : besoin, coordonnées cliquables, conversation, lien de l'espace client, bouton « Marquer comme traitée » ;
  - SMS « Nouvelle demande de devis de Nom, 06… : résumé. Suivi : … » sur le mobile du commerçant, et un push à l'owner.
- Le bouton de l'email ouvre une page de confirmation (rien ne change) ; son bouton marque la demande traitée (la ligne passe « Traitée » dans le dashboard).
- Une simple question : l'email seulement, pas de SMS.
- Demande reçue pendant la plage « Ne pas déranger » (22 h – 8 h par défaut) : l'email tout de suite, le SMS à la fin de la plage.
- Laissée « À traiter » 24 h : un rappel, email « Rappel : Demande de devis — Nom » et SMS « Rappel, en attente depuis le … ». Après 48 h : push « Abonné X : N demandes non traitées depuis 48 h ».

### Espace client (R8)

- Prérequis : assistant livré, identité d'envoi ; un abonnement Stripe de test et le portail configuré dans Stripe pour la partie facturation (question 14).
- Assistants IA, « Envoyer l'espace client » : `POST …/{id}/client-link` (`send: true`), « Espace client envoyé à … », le lien est copié, et l'email « Votre espace : les demandes reçues par {prénom} » part à l'adresse du commerce.
- Ouvrir le lien `/client/{token}` : `GET …/client/{token}`, puis les sections Demandes, Rapport du mois, Réglages, Abonnement, Prochains rendez-vous, Connexions.
- « Marquer traitée » : `POST …/client/{token}/requests/{id}/handled`, et la demande passe « Traitée », dans le dashboard aussi.
- Réglages : changer le prénom, « Enregistrer » : `PATCH …/client/{token}/settings`, « Enregistré. », et le widget se présente sous le nouveau prénom au rechargement.
- Changer le mobile d'alerte : l'email « Votre mobile d'alerte a été modifié » part à l'adresse du commerce, et le journal d'activité de l'owner le note. Un fixe, ou un mobile hors France, Belgique, Luxembourg, Suisse et Allemagne, est refusé.
- « Factures, carte bancaire, résiliation » : `POST …/client/{token}/billing-portal`, puis le portail Stripe. Sans portail configuré : message « indisponible ».
- La page n'envoie rien à PostHog et ne transmet pas son adresse en referrer (onglet Réseau).

### Rendez-vous dans Google Agenda (R2b)

- Prérequis : assistant livré ; `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` et `GOOGLE_CALENDAR_REDIRECT_URI` déclarée dans la console Google, accès `calendar.events` et `calendar.freebusy` sur l'écran de consentement, votre compte parmi les testeurs (question 18).
- Espace client, Connexions, « Connecter Google Agenda » : `POST …/client/{token}/calendar/connect`, consentement Google dans un nouvel onglet (laisser les deux cases de l'agenda cochées), puis la page « fermez cet onglet ».
- De retour sur l'espace (il se recharge) : « Agenda connecté » et l'adresse du compte. L'email « Votre agenda Google est connecté » part à l'adresse du commerce.
- Réglages de l'agenda (durée, délai minimum, types un par ligne, agenda utilisé) : `PATCH …/client/{token}/calendar`.
- `/ia/{slug}?internal=1`, « Prendre rendez-vous » : `GET …/appointment-slots` (`mode: "calendar"`, 3 `times`). « Autres créneaux » : la page suivante.
- Choisir un type et un créneau, laisser votre mobile : `POST …/lead` avec `booking`, puis « C'est réservé : jeu. 1 oct., 14:00 (Révision). Vous recevez une confirmation par SMS. ».
- Dans Google Agenda : l'événement « [Test] Révision — Nom », le contact et le besoin en notes. Sur votre mobile : « {Commerce} : votre rendez-vous du jeu. 01/10 à 14:00 (Révision) est confirmé. Empêché ? Appelez le … ».
- Sans `?internal=1`, en plus : le SMS au commerçant « RDV réservé le jeu. 01/10 à 14:00 (Révision) par Nom, 06… » et l'email « Rendez-vous réservé — Nom » avec le bloc « Dans votre agenda ».
- Créneau pris entre-temps (un événement ajouté à la main sur le créneau proposé) : 409, « Ce créneau vient d'être pris. Choisissez-en un autre. », puis une nouvelle offre.
- Rappel J-1 : délai minimum à 0 h, réserver demain à une heure comprise entre 9 h et 19 h et au moins 2 h plus tard que maintenant. Le SMS « Rappel : rendez-vous demain, … » part aujourd'hui à cette heure-là (boucle de 5 min).
- « Déconnecter » : `DELETE …/client/{token}/calendar`, et le widget repasse aux demi-journées.

### Rapport mensuel (R9)

- Prérequis : assistant livré par un paiement Stripe de test (le rapport exige un abonnement en cours), paiement reculé : `UPDATE ai_assistant_subscriptions SET activated_at = '2026-08-01' WHERE ai_assistant_id = 42;` ; identité d'envoi ; quelques conversations et demandes du mois **sans** `?internal=1` (une visite interne n'entre pas dans les chiffres) ; clé de modèle pour « Ce que vos visiteurs demandent le plus » (3 conversations au moins).
- Envoi normal : le 1er du mois à partir de 8 h (boucle de 10 min, jusqu'au 3), pour un abonnement payé au moins 7 jours avant la fin du mois.
- Envoi forcé, depuis `api/`, sur un assistant de test seulement (le mois reste marqué envoyé) : `python -c "import asyncio; from datetime import date; from core.database import SessionLocal; from models.ai_assistant import AiAssistant; from services.ai_assistant.report_service import ReportPeriod, ai_assistant_report_service as s; db = SessionLocal(); print(asyncio.run(s.report(db, db.get(AiAssistant, 42), ReportPeriod.of_month(date(2026, 9, 1)))))"` (42 : l'id de l'assistant). Il affiche `True`, puis `False` si on le relance (supprimer la ligne `ai_assistant_reports` pour rejouer).
- Email « {prénom} en septembre : N demandes, … » à l'adresse du commerce, l'owner en copie cachée : bandeau à la couleur du widget, chiffres, questions les plus posées, lien de l'espace client. L'espace client le montre sous « Rapport du mois ».
- Mois sans visite (la même commande sur août, `date(2026, 8, 1)`, où l'assistant n'avait aucune visite) : l'autre email (vérifier la bulle sur le site, le lien de la fiche Google) et le push « Abonné X : aucune visite en août 2026 (risque de désabonnement) ».
- Pastille « Risque de désabonnement » sur la carte : un assistant livré au paiement reculé de plus de 30 jours, sans conversation ni demande depuis 30 jours.

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
- **Jeu de caractères et dates** (`fix: declare utf8mb4 on every receptionist table`) :
  - Changé :
    - les 8 tables de la réceptionniste (conversations, messages, demandes, photos, rapports, agendas, rendez-vous, documents) sont déclarées en `utf8mb4_unicode_ci` par une constante commune, `UTF8MB4_TABLE_OPTIONS`. Un test vérifie le DDL MySQL de chacune ;
    - les dates d'abonnement reçues de Stripe (`current_period_end`, `canceled_at`) sont enregistrées en UTC naïf, comme les autres dates.
  - Vu et laissé :
    - la déclaration ne joue qu'à la création d'une table. Les 6 tables nouvelles de la branche naîtront donc en utf8mb4. Les conversations et les messages, déjà en prod, ne sont pas convertis : la vérification de la question 24 reste valable pour elles.
    - Relu sans changement : les migrations sont idempotentes (checkfirst, colonnes nullables, recopie des leads en `NOT EXISTS`) et `MIGRATION_MODULES` est complet et dans l'ordre.
    - Relu sans changement : le fuseau de Paris est lu par zoneinfo avec un repli UTC, mais en double (`opening_hours`, `knowledge_builder`). Ce doublon est traité en passe 3.
- **Relecture du diff** (`2ec40bb` → `95ae98e` : 6 `fix`, 18 `refactor`). Le skill `relecture` n'existe pas dans cet environnement : cinq relectures en parallèle ont lu le diff fichier par fichier contre les trois `STANDARDS_CODE_ET_ARCHITECTURE.md`.
  - Bugs corrigés, chacun avec un test ou une vérification Chromium avant / après :
    - volet Sources qui écrivait après sa fermeture (erreur « Cannot read properties of null », PDF ajouté à un autre assistant) ;
    - réglages non enregistrés de l'espace client effacés au retour de l'onglet Google ;
    - « urgency » en liste renvoyée par le modèle vision (erreur 500) ;
    - historique de chat finissant par un tour de l'assistante, journalisé comme message du visiteur ;
    - SMS de confirmation ou de rappel refusé dès que le nom du commerce contient un caractère hors GSM-7 (« N°1 ») ;
    - lien client expiré depuis plus de 90 jours qui proposait un renouvellement impossible.
  - Nettoyé :
    - fuseau de Paris et dates courtes en un seul endroit (`OpeningHoursCalendar`, `FrenchDateFormatter`) ;
    - signature HMAC commune aux trois liens signés, formats inchangés (un test les fige) ;
    - `calendar_service.py` (1133 lignes) découpé en réglages, grille des créneaux, accès Google, réservation et connexion ;
    - routes de `ai_assistants.py` (1143 lignes) découpées en propriétaire, demandes, abonnements et widget, plus `ai_assistant_common.py`. Mêmes 42 routes, dans le même ordre de correspondance ;
    - envoi au commerçant par un seul `AiAssistantBusinessMailer` ;
    - fixtures et doublures de test partagées (`tests/conftest.py`, `tests/assistant_fakes.py`) ;
    - web : `UiChipToggleGroup`, `postMultipart`, formateur de date partagé ;
    - demo-host : utilitaires de refus API, de nom court et d'accent, libellés du widget en constantes, composants communs de l'espace client.
  - Vu et laissé :
    - le `_utc_now()` par module est la convention du dépôt (`_utcnow` dans trois services de `main`) ;
    - les bandeaux `# ── … ─` de `sms/templates.py` sont ceux du fichier sur `main` ;
    - les points d'interface (états vides et d'erreur, boutons, badge, emoji) sont traités en passe 4 ;
    - la suppression des bandeaux de `test_assistant_calendar.py` est partie avec `2db1158` ;
    - le reste est listé juste en dessous.
- **Interface** (`edd0596` → `02d5def`, un commit par écran). Le skill `ui-ux-pro-max` n'existe pas dans cet environnement : chaque écran est aligné sur ses voisins de l'Atelier (Abonnements, Utilisateurs, Commandes, le volet Conversations, le volet des signatures email).
  - Changé :
    - Assistants IA :
      - KPI en `UiStatCard`, avec `UiLoader` pendant le chargement et `UiEmptyState` quand il n'y a pas de demande ;
      - onglets posés sur la ligne de séparation ;
      - « Risque de désabonnement » au lieu de « churn », dans le style des autres pastilles de la carte, qui passent sous le nom quand la place manque ;
      - chiffres de la carte en gris : la couleur est gardée pour les statuts ;
      - boutons désactivés visibles.
    - Personnaliser : « IA hébergée en Europe (Mistral) ». Le refus de l'API et les alertes admin disent la même chose.
    - Volet Sources :
      - état d'erreur avec « Réessayer » ;
      - suppression confirmée par `UiConfirmModal`, comme dans les autres volets ;
      - boutons désactivés visibles.
    - Widget :
      - puces photo et rendez-vous dessinées avec les icônes de la barre de saisie, sans emoji. « Photo envoyée » n'a plus d'emoji non plus, dans le journal comme dans le widget ;
      - texte indicatif court, sur une ligne à 375 px ;
      - le panneau photo masque les suggestions, comme celui des créneaux : la barre de saisie sortait de la fenêtre de 680 px.
    - /ia : deux-points insécables.
  - Vérifié : dans Chromium, à 1280 et 375 px, en clair et en sombre, avec l'API simulée. Pas de défilement horizontal. Le demo-host n'a pas de thème sombre : rien ne change.
  - Vu et laissé :
    - l'espace client est déjà aligné : jetons de /ia, états vides, de chargement et d'erreur présents ;
    - le volet Conversations et la page Abonnements ne sont pas touchés par la branche. Le badge de désabonnement est sur les cartes Assistants IA.
- **Documentation** (`da2e58f`, `f8b4820`, puis le commit de ce parcours) :
  - Changé :
    - `ASSISTANT_MODULE.md` suit le cycle de vie du produit : génération, connaissance, démo, vente, après-vente, alertes et rapports, espace client, puis une partie Référence (endpoints, statuts servis publiquement, dashboard, tracking, carte des fichiers) ;
    - doublons retirés : la page `/a/{slug}`, qui n'existe plus, fondue dans « Page de démo `/ia/{slug}` » ; le prix de la démo, le verrou de 45 jours et le suivi PostHog, chacun décrit une seule fois ;
    - contradictions corrigées : 6 routes manquaient au tableau des endpoints (conversations, abonnements, lien d'abonnement) ; le lien d'abonnement accepte une démo expirée ; la section Tracking oubliait 2 events PostHog ; les renvois « section suivante » ne tombaient plus juste ; « EU only » et « churn » sont devenus « IA hébergée en Europe » et « risque de désabonnement » ;
    - retirés : numéros de ticket, prénoms, plan de code (« multi-tenant plus tard ») ;
    - passation : « Parcours de test manuel », un parcours par fonctionnalité, juste après « Rejouer ».
  - Vu et laissé :
    - les exemples de messages gardent des visiteurs fictifs (« Marc », « Julie Roux ») et la persona par défaut « Sofia » : ce sont des données d'exemple, pas des personnes ;
    - le widget refuse une photo illisible en demandant « JPEG ou PNG », alors que le serveur accepte aussi WEBP : texte d'interface, hors de cette passe ;
    - aucun parcours n'a été joué contre de vrais services : pas de clés dans cet environnement.
- **Vérification finale** (après les cinq passes) : tests, ruff et lints relancés sur la branche entière. `ruff format --check` a trouvé une ligne trop longue laissée par `2e5d87c` dans `assistant_service.py`, reformatée par `5d962ab` (le message ne change pas). Le reste est dans l'état attendu : 1138 passed et 2 des 3 échecs préexistants, ruff propre, prettier et eslint propres, typecheck avec ses 5 et 2 erreurs préexistantes.

### Relecture : points laissés pour plus tard

🟡 À faire dans une passe dédiée (plus gros, ou discutable) :
- **Fichiers encore longs** :
  - `appointment_notices.py` (674 lignes) : sortir les textes et l'ICS dans `appointment_texts.py` ;
  - `request_alerts.py` : sortir `AlertSms` et `AlertSettings` ;
  - `report_service.py` : sortir les chiffres dans `report_stats.py` ;
  - `photo_service.py` : sortir la vision dans `photo_vision.py` ;
  - `request_service.py` : sortir l'annonce dans `request_follow_up.py`, ce qui casse le cycle d'import avec `request_alerts` ;
  - `knowledge_builder.py` : sortir les sources ;
  - `calendar_booking.py` : 434 lignes, surtout des docstrings ;
  - `test_assistant_calendar.py` : 1 250 lignes, à découper par thème.
- **Doublons restants** :
  - troisième client OAuth Google, avec Postmaster et Gmail : un `GoogleOAuthClient` commun ;
  - construction des appels Mistral et Groq : un `LlmCompletion.from_response` ;
  - `_claim`, `_send_sms` et le journal d'activité, copiés entre `appointment_notices`, `request_alerts`, `report_service` et `client_space_service` ;
  - garde-fous de `send_service_message`, repris de `send_manual`.
- **`client_ip`** prend la première adresse de `X-Forwarded-For`. Si nginx ajoute l'adresse réelle à la fin, un visiteur peut contourner les limites par IP. À vérifier dans la config nginx (hors dépôt) ; sinon, passer à `request.client.host`, uvicorn tournant avec `--proxy-headers`.
- **Contrats** :
  - le widget reconnaît un créneau retiré à n'importe quel 422 à détail texte : un code d'erreur dédié serait plus sûr ;
  - les limites 255 / 2000 / 64 sont écrites à la fois dans les schémas et les services ;
  - les noms d'enums mélangent `AiAssistant*` et `Assistant*` ;
  - les types de stockage de la page admin n'ont pas d'enum.
- **Web** :
  - `ai-assistants.vue` fait encore environ 1 100 lignes : sortir la boîte des demandes en composant, la modale Personnaliser en drawer, les KPI en `UiMiniStat` ;
  - l'onglet « À traiter » compte la liste, bornée à 300, et le KPI compte l'API ;
  - les photos s'ouvrent dans un onglet au lieu de `UiImageLightbox` ;
  - `aria-pressed` manque sur les puces ;
  - l'en-tête de drawer est copié entre les volets.
- **Demo-host** :
  - `AssistantChat.vue` fait encore environ 1 470 lignes : sortir le panneau de créneaux et le panneau photo, et un `useAssistantBooking` ;
  - la section Abonnement de l'espace client n'est pas encore un composant ;
  - « Enregistré. » reste affiché après déconnexion puis reconnexion de l'agenda ;
  - la section Connexions montre « Bientôt » et l'identifiant « primary » à un client payant ;
  - « 8 Mo », « 3 photos » et « 90 jours » sont écrits dans les textes au lieu de venir des constantes.
- **Rappel J-1** : sa fenêtre est 9 h – 19 h à la réservation et 9 h – 20 h à l'envoi. L'écart laisse une marge à la boucle, mais la règle vit dans deux classes.

⚪ Détails notés :
- quelques noms vagues restent (`result`, `data`, `item` dans `mistral_service`, `document_service`, `appointment_notices`) ;
- des booléens n'ont pas de préfixe `is_` : `PhotoAnalysis.relevant`, `ExtractedDocument.truncated`, `shrank()` ;
- des `isnot` sont à remplacer par `is_not` ;
- `init_db()` ne liste que 3 des 6 nouveaux modèles, et `models.__all__` n'a ni conversation ni message ; sans effet, `models/__init__` les importe tous ;
- la conversion latin1 → utf8mb4 de la migration des documents est devenue inutile ;
- les docstrings de `cleanup_service` ne parlent que des démos ;
- la carte des clés R2 (`r2_storage_service`) n'a pas la ligne des documents ;
- côté `main`, hors branche : le lecteur de site ne filtre pas les adresses internes (une tâche est proposée).

## Relecture finale (25/09) — corrections avant fusion

Sept relectures parallèles (surface publique, demandes et alertes, agenda, connaissance et abonnements,
migrations et fichiers partagés, dashboard, demo-host) ont relu tout le diff `main...feat/receptionist-phase-1`,
puis chaque écran a été cliqué en local (API sur SQLite, dashboard, page `/ia`, widget embarqué, espace
client, à 1280 et 375 px). Neuf commits de correction sont posés sur la branche ; la fusion avec la branche
R12 (`claude/epic-bohr-lgv8d8`) est préparée sur `release/receptionist-phase-1` (un seul conflit, le registre
des migrations). Tests sur la branche de release, R12 comprise : 1 230 verts, 4 écartés (les 3 échecs
préexistants) et `test_window_expiry_frees_budget`, sensible au temps sous Windows (il passe sur `main` une
fois sur deux) ; ruff, prettier, eslint et typecheck propres sur les trois projets.

**Surface publique** (`15e620d`)
- L'adresse d'un visiteur est la dernière de `X-Forwarded-For` (celle que nginx ajoute), plus la première :
  un en-tête forgé ne contourne plus les limites par IP (chat, photos, demandes, abonnement, liens signés).
- Le limiteur en mémoire oublie la moitié la plus ancienne de ses clés au lieu de tout effacer.
- Une visite `?internal=1` ne réserve jamais dans l'agenda d'un client (422 avec la phrase pour l'opérateur) :
  c'était le moyen de créer des événements et d'envoyer des SMS en silence.
- Les dates d'un `booking` et le paramètre `after` sont bornés (2020-2100 : un `9999-12-31` faisait une 500) ;
  un jeton « marquer traitée » non ASCII ne fait plus de 500 ; les champs de `PATCH /{id}` sont bornés.
- La configuration publique d'un assistant vendu ne porte plus le téléphone ni l'email de l'opérateur.
- Le chat rend sa connexion au pool pendant l'appel au modèle ; le quota photo est revérifié après le décodage.
- Les journaux des échecs d'écriture (demande, conversation) ne portent plus de traceback : une erreur SQL y
  recopiait le message ou les coordonnées du visiteur.

**Agenda** (`84cb59e`)
- Le rappel J-1 relit l'événement dans Google avant de partir : annulé ou supprimé → rien ; déplacé → la
  ligne suit, rappel seulement si c'est encore demain.
- Un 401 isolé est rejoué une fois après rafraîchissement du jeton ; l'agenda ne passe « à reconnecter » que
  sur un second refus ou un `invalid_grant`.
- La création de l'événement est retentée sur 5xx / 429 ; un événement déjà créé (réponse perdue, ligne non
  écrite) est repris, jamais recréé, au lieu d'un faux « créneau pris ».
- Un contact (mobile ou adresse) n'a qu'un rendez-vous à venir par assistant ; le plafond de 20 par jour est
  compté sous le verrou ; `request_id` est unique en base.
- Un créneau réservé sans agenda passe par la vérification des demi-journées (jour ouvert, à partir de
  demain) ; « ce créneau n'est plus proposé » répond 409 comme un créneau pris, et le widget ne lit plus
  n'importe quel 422 comme un créneau retiré.
- Les lignes « jour férié » des horaires ne servent plus d'horaires hebdomadaires ; un agenda introuvable est
  dit tel quel (plus « Google n'a pas répondu »).

**Demandes, alertes, SMS** (`0b31db6`)
- « Ne plus contacter » coupe tout envoi au commerce (email, SMS, rappels, rapport, lien d'espace).
- Une photo qui rend urgente une demande déjà annoncée déclenche le SMS.
- Un email de demande sans adresse, ou refusé par l'envoi, est inscrit au journal d'activité.
- Les mobiles d'alerte (dashboard et espace client) et les SMS aux visiteurs n'acceptent que des mobiles de
  France, Belgique, Luxembourg, Suisse ou Allemagne (`to_served_mobile`) : un fixe belge ou un mobile
  britannique ne passent plus.
- La liste STOP de prospection ne bloque plus les SMS de service (alertes payées, confirmation demandée).
- Le suivi d'une demande ne rétrograde plus une urgence lue entre-temps ; le résumé renvoyé en liste est joint ;
  « panne » ne classe plus « panneaux » en urgence ; le journal d'activité masque les mobiles (2 derniers
  chiffres) ; PNG et WEBP sont bornés à 30 Mpx ; le portail Stripe est appelé hors de la boucle d'événements.

**Abonnements, connaissance, modèles** (`2ce3adc`, `d179721`)
- Fin de période lue sur `items.data[].current_period_end` (API Basil) : la colonne restait vide.
- `customer.subscription.deleted` passe l'assistant `expired` (widget muet, plus d'alerte ni de lien).
- Un assistant sans adresse prend celle du paiement Stripe à la vente ; l'opérateur règle l'adresse des alertes
  dans « Personnaliser » (`PATCH /{id}` accepte `email`).
- Une requête que Mistral refuse (modèle mal nommé…) alerte les admins ; le lecteur de site borne chaque page
  à 2 Mo et parse hors de la boucle ; le lecteur de PDF ne reçoit plus les secrets de l'API ; les avis Google
  sont encadrés comme données ; un site d'une page est protégé contre une relecture vide.

**Migrations et déploiement** (`3ec42ce`)
- `convert_ai_assistant_tables_to_utf8mb4` convertit au déploiement les tables `ai_assistant*` encore en
  latin1 (conversations et messages de la phase 0 : un emoji y faisait perdre la conversation).
- `raise_assistant_default_price` n'imprime plus les adresses ; `rewrite_assistant_emails_missed_requests` ne
  réécrit que les modèles encore au texte semé (un modèle retouché à la main est gardé).
- `deploy-api.yml` écrit `GOOGLE_CALENDAR_REDIRECT_URI` et `MISTRAL_API_KEY` dans le `.env` de prod (le secret
  GitHub `MISTRAL_API_KEY` reste à créer ; sans lui, tout reste sur Groq).

**Dashboard** (`4c77798`)
- « Personnaliser » est un volet de la pile (`UiAssistantSettingsDrawer`), avec l'email du commerçant, une
  langue au moins, le mobile borné, l'état SMS sans mobile expliqué ; la page a perdu sa modale.
- L'onglet « À traiter » lit `?status=new` : il montre toutes les demandes nouvelles, le KPI et l'onglet disent
  le même chiffre ; « Toutes » indique quand seules les 300 dernières sont affichées.
- Supprimer un assistant retire ses demandes et ferme ses volets ; le sondage vidéo ne masque plus la page ;
  « Envoyer l'espace client » demande confirmation ; le contact d'une demande est entier et cliquable
  (`tel:` / `mailto:`) ; statuts tous libellés ; couleur réservée aux statuts ; état d'erreur avec
  « Réessayer » ; le volet Sources repart propre d'un assistant à l'autre, vérifie type et taille du PDF avant
  l'envoi, et sa confirmation de suppression ne survit plus à sa fermeture ; `UiChipToggleGroup` porte
  `aria-pressed` ; filtre « Documents assistants » sur la page Stockage.

**Demo-host** (`bc8cf5d`)
- `/embed/**` répond `frame-ancestors *` : l'iframe du widget était refusée sur tout site client (la CSP du
  demo-host ne laissait que le dashboard et Storyblok).
- L'accès à `localStorage` est dans le `try` : un navigateur qui refuse le stockage à l'iframe tierce cassait
  tout le montage du widget.
- L'accent du client donne trois couleurs calculées (fond, encre dessus, texte sur papier clair) : un accent
  clair reste lisible.
- « Être rappelé » oublie un créneau choisi avant ; changer de page de créneaux oublie l'heure choisie ; une
  photo refusée perd sa vignette ; PNG transparent sur fond blanc ; seuls les messages du parent sont écoutés.
- Accessibilité : `role="dialog"`, Échap ferme, focus dans le panneau à l'ouverture et sur la bulle à la
  fermeture, `aria-live` sur les messages, libellés et `autocomplete` sur le formulaire.
- Le loader borne la hauteur de l'iframe et passe en plein écran sous 640 px de haut (téléphone en paysage) ;
  le widget suit la même règle ; formulaire et créneaux défilent dans le panneau ; zones tactiles ≥ 36 px.
- Espace client : champs figés pendant l'enregistrement ; « Enregistré. » disparaît à la déconnexion de
  l'agenda ; `mailto:` refuse `?` et `&` ; le replay PostHog masque les bulles du chat ; l'import PostHog n'a
  plus de chemin Windows absolu (le typecheck cassait sur une autre machine).

**Décisions prises à la relecture** (à contester si besoin)
- Résiliation = fin de service immédiate (question 11).
- Une visite de test ne réserve jamais dans un agenda ; le test d'acceptation Google se joue sans `internal`.
- Les SMS de service ignorent la liste STOP de prospection.
- Un prospect « ne plus contacter » garde son assistant servi, mais n'est plus écrit.

**Ce qui attend Léo avant de pousser `main`**
- La question 9 (prix) : le déploiement lance `raise_assistant_default_price` (29 → 79 € sur les comptes
  restés au défaut) et la réécriture des cinq emails « Assistant IA » ; les relances J+3 de la vague du 22/09
  diraient 79 € après un premier email à 29 €.
- `deploy-api.yml` se déclenche aussi sur `pull_request` vers `main` (sans garde) : **ne pas ouvrir de PR**
  pour cette branche, elle déploierait la prod avant relecture ; fusionner et pousser `main` directement.
- Le dépôt GitHub a déménagé (`DevLeadHunter/devleadhunter`) : le remote local répond encore par redirection,
  à mettre à jour (`git remote set-url`).
- Secrets et réglages hors dépôt : `MISTRAL_API_KEY` (secret GitHub), accès `calendar.events` +
  `calendar.freebusy` et redirect URI dans la console Google, `client_max_body_size` ≥ 9 Mo dans nginx,
  portail Stripe configuré.

**Laissé pour plus tard** (en plus de « Relecture : points laissés pour plus tard »)
- Ordre des webhooks Stripe (un `incomplete` livré en retard peut rétrograder une ligne payée) ; prix
  « verrouillé » qui peut différer du prix payé si deux Checkout se chevauchent.
- Page SMS : les SMS de service se mêlent aux SMS de prospection dans la liste et les compteurs.
- Retour Google quand le nouvel onglet est bloqué : la page de l'API n'a pas de lien retour.
- `createImageBitmap` avec redimensionnement pour décoder les très grandes photos côté navigateur.
- Bench (`scripts/bench_assistant_llm.py`) qui ignore `eu_only` ; polices Google chargées sur l'espace client.
- `AssistantChat.vue` (~1 500 lignes) et `ai-assistants.vue` (~1 000 lignes) restent à découper.

## Refonte des écrans et déploiement (nuit du 25 au 26/09)

Mandat de Léo le 25/09 au soir : « finis le module à 100 %, demain je n'ai plus qu'à tester et peaufiner » ; le
widget et la page /ia « ne faisaient pas pro », loin du niveau du module Sites web, qui devait servir de modèle.

**Déployé sur `main`** (API, web, demo-host, desktop verts) :

- `a3fa59a` : fusion de `release/receptionist-phase-1`. Les migrations de la phase 1 ont tourné en prod : prix
  29 → 79 € sur les comptes au défaut, les 5 emails « Assistant IA » réécrits, tables `ai_assistant*` déjà en
  utf8mb4. La question 9 est donc tranchée par le déploiement.
- `16973e1` : refonte du widget, de la page /ia et des trois écrans du dashboard (détail dans
  `docs/ASSISTANT_MODULE.md`, sections « Le widget », « Page de démo » et « Dashboard »).
  - **Widget** : en-tête en dégradé de l'accent (avatar, prénom en Fraunces, « en ligne »), puces d'action dans le
    fil avant le premier échange, cartes photo / créneaux / coordonnées dans le fil, boutons ronds ; palette
    `AssistantAccentUtils.palette()` ; mode `inline` et émission `lead-sent` pour la page de démo.
  - **Page /ia** : la maquette « deux téléphones » validée le 24/09 : fiche Google stylisée, téléphone du client
    avec le vrai widget, téléphone du patron avec la notification qui reprend la vraie demande envoyée
    (`AssistantDemoScenario.ts`), trois résultats, estimation, pilule de prix, signature.
  - **Dashboard** : page liste (cartes avec aperçu iframe, compteurs, recherche, filtre), page de détail
    (`/dashboard/ai-assistants/{id}` : résumé, script à coller, actions, dernières demandes), boîte de réception
    `/dashboard/ai-assistants/requests` (entrée « Demandes » de la nav) et volet Demande avec transcription et note.
  - **API** : `GET /ai-assistants/{id}`, `GET /ai-assistants/requests/{id}` (demande + transcription), champs
    publics `city`, `trade_label`, `google_rating`, `google_reviews_count`.
- Petits points : la ligne de rôle de l'en-tête du widget tient sur deux lignes au lieu d'être tronquée ; la CSP
  du demo-host autorise `http://localhost:5173` (aperçus des cartes en local).

**À tester par Léo** (toujours avec `?internal=1` sur les pages du demo-host) : `/ia/{slug}` sur desktop et
mobile (une demande envoyée depuis le téléphone de gauche doit mettre à jour la notification de droite), le widget
embarqué (`/embed-test.html?slug=…&internal=1`), puis `/dashboard/ai-assistants`, la page de détail et
`/dashboard/ai-assistants/requests` (ouvrir une demande, lire la transcription, noter, marquer traitée).

**Restes** : `AssistantChat.vue` fait encore ~1 300 lignes (à découper en composants), l'aperçu de carte charge la
page /ia entière (léger avec quelques assistants, à remplacer par une capture si la liste grandit), avatar de Léa,
photos d'exemple par métier, cartes Asana à passer en Terminé à la main, prérequis hors dépôt inchangés (secret
`MISTRAL_API_KEY`, scopes et redirect URI Google, `client_max_body_size` nginx, portail Stripe).

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
9. **Relances à 79 €** : un prospect qui a reçu un email à 29 € voit 79 € dans les relances, sur la démo et au paiement. **Tranché par le déploiement du 25/09 au soir** : `main` poussé, la migration de prix a tourné (voir « Refonte des écrans et déploiement »). Si le prix doit revenir à 29 € pour les relances en cours : Paramètres → Facturation.
10. **Scoring prospect** : brancher les événements de /ia et les demandes de l'assistant dans `behavior_service` ?
11. **Résiliation** : tranché à la relecture. Sur `customer.subscription.deleted`, l'assistant passe `expired` : widget muet, plus d'alerte, de rapport ni de lien d'espace ; un nouveau paiement le remet `delivered`. À revoir si tu préfères une période de grâce.
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
24. **Jeu de caractères des tables de la phase 1** : réglé à la relecture par la migration `convert_ai_assistant_tables_to_utf8mb4` (idempotente, MySQL seulement), qui convertit au déploiement toute table `ai_assistant*` encore en latin1 (les conversations et messages créés le 24/09 en font partie). Après le déploiement, vérifier : `SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME LIKE 'ai_assistant%' AND TABLE_COLLATION NOT LIKE 'utf8mb4%';` doit ne rien renvoyer.

## Petits points laissés en l'état

- L'email de résumé R3 dit toujours « votre réceptionniste virtuelle », même pour un prénom masculin. Le rapport R9 accorde déjà via `resolve_persona_gender` ; il suffit d'en faire autant dans `request_email.py`.
- `api/.env.example` (ligne existante, non modifiée) propose `GROQ_MODEL=llama-3.3-70b-versatile`, un modèle retiré le 2026-06-17 selon `core/config.py`. Il faut le supprimer ou le remplacer par `openai/gpt-oss-120b`.
- `HTTP_413_REQUEST_ENTITY_TOO_LARGE` (route photo) est déprécié à partir de Starlette 0.48 (simple avertissement). Tout le code l'utilise encore ; le remplacer partout d'un coup.
- Le journal des conversations n'affiche pas la marque « test ».
- Créneaux ajoutés après l'annonce : un visiteur qui recharge la page et choisit des créneaux dans les 24 h met à jour sa demande déjà annoncée ; le commerçant les voit dans le dashboard et l'espace client, pas dans un nouvel email ni un nouveau SMS (seulement dans le rappel J+1).

