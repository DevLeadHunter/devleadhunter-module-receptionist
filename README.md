# DevLeadHunter — module Réceptionniste IA

La réceptionniste IA de DevLeadHunter : un assistant multilingue préparé pour chaque prospect (widget sur son site,
page de démo, espace client, demandes et rendez-vous, alertes, vidéo de prospection), vendu par abonnement.

Ce dépôt est un **module produit** : il ne tourne pas seul. Le cœur,
[`DevLeadHunter/devleadhunter`](https://github.com/DevLeadHunter/devleadhunter), l'installe à la version épinglée
dans son `product-modules.json`, et le super admin l'active ou le coupe dans **Paramètres → Administration →
Modules**. L'architecture est décrite dans le
[`docs/PRODUCT_MODULES.md`](https://github.com/DevLeadHunter/devleadhunter/blob/main/docs/PRODUCT_MODULES.md) du cœur.

| Dossier | Contenu | Utilisé par le cœur |
| --- | --- | --- |
| `api/` | Paquet Python `devleadhunter-receptionist` (`devleadhunter_receptionist/`) : modèles et migrations, routes `/ai-assistants/…`, `/public/{slug}/…`, `/client/{token}/…`, tâches de fond, offre de campagne, modèles d'emails et de SMS, route du sidecar desktop | installé par `pip` au déploiement (entry point `devleadhunter.product_modules`) |
| `web/` | Layer Nuxt du dashboard : réceptionnistes, atelier, demandes, réglages | étendu par `web/nuxt.config.ts` |
| `demo-host/` | Layer Nuxt des pages publiques : `/ia/:slug`, `/embed/:slug`, `/va/:slug`, `/client/:token` | étendu par `demo-host/nuxt.config.ts` |
| `docs/` | Doc fonctionnelle (`ASSISTANT_MODULE.md`), passation, argumentaire, maquettes (`docs/mockups/README.md`) | — |

Le code du module importe le cœur par ses noms habituels (`from models.prospect_db import ProspectDB`, `~/…` dans les
layers) : il tourne toujours avec le cœur.

## Développer

Cloner le module à côté du cœur, puis :

```bash
# Dans le venv de api/ du cœur
pip install -e ../devleadhunter-module-receptionist/api
```

```bash
# web/ et demo-host/ du cœur étendent alors le clone local (chemin absolu du dossier qui contient les clones)
export DLH_PRODUCT_MODULES_DIR=/chemin/vers/Projects
```

Les layers n'ont pas de `node_modules` à eux : relier `web/node_modules` et `demo-host/node_modules` de ce dépôt à
ceux du cœur (sous Windows, `mklink /J`, et les retirer avec `cmd /c rmdir`, jamais `rm -rf`). Ils sont ignorés par
git.

## Tests

Ils tournent depuis `api/` du cœur, sur ses fixtures :

```bash
cd ../devleadhunter/api && python -m pytest ../../devleadhunter-module-receptionist/api/tests
```

Les layers se vérifient avec le lint et le build du cœur, `DLH_PRODUCT_MODULES_DIR` posé.

## Publier une version

1. Taguer `main` de ce dépôt (`vX.Y.Z`) et pousser le tag.
2. Dans le cœur, passer `ref` à `vX.Y.Z` dans `product-modules.json` : le push sur `main` redéploie l'API, le
   dashboard, les démos et l'application PC avec cette version.
