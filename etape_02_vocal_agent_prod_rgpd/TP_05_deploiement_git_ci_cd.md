# TP 05 — CI/CD, Git Tagging et Déploiement (4h)

> **Version TP :** 1.0.0 — pipeline GitHub Actions (`release.yml` existant), déploiement Render.com, tests de non-régression en production
> **Mis à jour :** 2026-05-25

> **Prérequis :** TP 01 à TP 04 complétés · dépôt sur GitHub · compte Render.com (gratuit) · `GROQ_API_KEY`

> **Durée estimée :** 4 heures

---

> **Cas réel — Atlassian (avril 2022) :** Un script de maintenance prévu pour désactiver ~20 comptes inactifs s'exécute avec les mauvais identifiants et supprime définitivement les données de ~400 clients cloud (Jira, Confluence, Bitbucket). La restauration a pris jusqu'à 14 jours pour certains clients. Cause : aucun test en staging, aucune validation croisée avant exécution, aucun mécanisme de rollback. **Mettre en production sans pipeline CI/CD testé expose aux mêmes risques** : un changement de prompt mal validé peut dégrader silencieusement le comportement de votre agent pour tous vos utilisateurs.

---

## Partie 1 — Versionnement sémantique et tags git (1h)

### 1.1 Comprendre le versionnement sémantique

Le versionnement sémantique (semver) suit le format `MAJOR.MINOR.PATCH` :

| Incrément | Quand l'utiliser | Exemple |
|---|---|---|
| `PATCH` | Correction de bug, aucun changement d'interface | `v1.0.0 → v1.0.1` |
| `MINOR` | Nouvelle fonctionnalité rétrocompatible | `v1.0.1 → v1.1.0` |
| `MAJOR` | Changement cassant (format d'API, suppression d'un champ) | `v1.1.0 → v2.0.0` |

Pour votre agent :
- Correction d'un cas dans `system_prompt.yaml` → PATCH
- Ajout d'un nouvel intent (ex : `reservation`) → MINOR
- Renommage d'un champ dans le payload `/api/text` → MAJOR

**Questions :**
1. Le dépôt n'a encore aucun tag. Vous corrigez un bug dans `system_prompt.yaml` (règle de négation). Quel serait le premier tag git de release ? (Note : le numéro de version interne de `system_prompt.yaml` — `v1.6.0` — est indépendant du tag git du dépôt.)
2. Vous ajoutez la gestion des réservations à date sans casser l'API existante. Quel serait le tag suivant ?
3. Vous renommez le champ `response_text` en `text` dans la réponse JSON de `/api/text`. Quel serait le tag ? Pourquoi ?
4. Quel fichier dans le dépôt devrait être mis à jour à chaque release pour documenter les changements ? Ce fichier existe-t-il déjà dans votre projet ?

---

### 1.2 Créer et pousser un tag de release

**Vérifiez d'abord que tous les tests passent :**

```bash
pytest tests/ -m "not slow" -v
```

**Créez un tag annoté et poussez-le :**

```bash
git tag -a v1.0.0 -m "Release v1.0.0 - agent vocal Traiteur Dupont"
git push origin v1.0.0
```

Rendez-vous dans l'onglet **Actions** de votre dépôt GitHub pour observer le pipeline se déclencher.

**Questions :**
1. Quelle est la différence entre un tag annoté (`git tag -a`) et un tag simple (`git tag`) ?
2. Dans `.github/workflows/release.yml`, quelle ligne déclenche le pipeline sur un push de tag ?
3. Après avoir poussé le tag, combien de jobs se lancent immédiatement ? Lesquels sont conditionnels aux tags uniquement ?
4. Vous avez fait une erreur et voulez supprimer le tag. Quelles commandes suppriment le tag localement ET sur le dépôt distant ?

---

### 1.3 Protéger la branche main

Sur votre dépôt GitHub : **Settings → Branches → Add branch protection rule**

Configurez la règle pour `main` :
- [x] Require a pull request before merging
- [x] Require status checks to pass before merging
  - Ajouter : `Lint (ruff)` et `Tests unitaires (pytest)`
- [x] Require branches to be up to date before merging

**Questions :**
1. Pourquoi protéger `main` avec des status checks ?
2. Qu'est-ce qu'une Pull Request et pourquoi est-elle préférable à un push direct sur `main` en équipe ?
3. Si un collaborateur pousse du code qui fait échouer `pytest`, que se passe-t-il avec la protection activée ?
4. Y a-t-il un risque à protéger `main` quand vous travaillez seul sur votre dépôt ? Comment contourner si vous êtes bloqué ?

---

## Partie 2 — Analyser le pipeline CI/CD existant (1h)

### 2.1 Lire le workflow GitHub Actions

Ouvrez `.github/workflows/release.yml`. Le pipeline contient 6 jobs organisés en DAG (graphe orienté acyclique) :

```
lint ──────────────────────────────────────┐
                                           ▼
unit-tests ──────────────────────► docker-build ──► prompt-tests ──► conversation-tests
           └─────────────────────► docker-release  (tags v*.*.* seulement)
```

`lint` et `unit-tests` s'exécutent **en parallèle** dès le déclenchement. `docker-build` attend que les deux réussissent.

**Questions :**
1. Quel mot-clé YAML dans la définition d'un job indique qu'il doit attendre la réussite d'un autre job ?
2. Le job `prompt-tests` ne s'exécute pas sur chaque commit. Regardez son champ `if:` — dans quelles conditions s'exécute-t-il exactement ?
3. Le job `docker-release` utilise `permissions: packages: write`. À quoi sert cette permission ?
4. Pourquoi les tests de conversation (`conversation-tests`) sont-ils dans un job séparé de `unit-tests` ?
5. Quel est le format complet de l'image Docker publiée ? (regardez `IMAGE_NAME` et le job `docker-release`)

---

### 2.2 Configurer les secrets GitHub

Les secrets sont des variables d'environnement chiffrées, injectées dans les jobs au moment de l'exécution. Ils ne sont jamais visibles dans les logs.

**Sur GitHub : Settings → Secrets and variables → Actions → New repository secret**

Ajoutez :
- **`GROQ_API_KEY`** : votre clé API Groq (copiez depuis votre `.env`)

> `GITHUB_TOKEN` est fourni automatiquement par GitHub dans tous les workflows — vous n'avez pas à le créer.

**Questions :**
1. Dans le workflow, dans quel job et comment la variable `GROQ_API_KEY` est-elle injectée dans l'environnement ?
2. Pourquoi ne pas mettre directement `GROQ_API_KEY: sk-...` en clair dans le fichier YAML du workflow ?
3. Qu'est-ce que `${{ secrets.GITHUB_TOKEN }}` et à quoi sert-il concrètement dans `docker-release` ?
4. Un contributeur externe fork votre dépôt et soumet une Pull Request. A-t-il accès à vos secrets dans les jobs CI ? Pourquoi est-ce important ?

---

### 2.3 Déclencher le pipeline sur un tag

Après avoir configuré les secrets, créez un second tag pour déclencher le pipeline complet :

```bash
git tag -a v1.0.1 -m "Release v1.0.1 - secrets et pipeline CI/CD configurés"
git push origin v1.0.1
```

Observez dans l'onglet **Actions** : les jobs en parallèle, ceux qui s'activent conditionnellement, et le temps total.

**Questions :**
1. Quel job prend le plus de temps ? Pourquoi ?
2. Le job `docker-release` a-t-il réussi ? Où est stockée l'image résultante (quel registre, quelle URL) ?
3. Que se passe-t-il si `unit-tests` échoue ? Les jobs `docker-build` et `docker-release` s'exécutent-ils quand même ?
4. Comment consulter les logs d'un step précis dans GitHub Actions ?

---

## Partie 3 — Déployer sur Render.com (1h30)

### 3.1 Créer le service sur Render

> **Pourquoi Render et pas Docker local ?** Le service est accessible depuis internet sans VPN ni port forwarding. Vos utilisateurs (et vos étudiants) peuvent tester l'agent depuis n'importe où avec n'importe quel navigateur.

**Étape 1 — Créer un compte sur [render.com](https://render.com)**

**Étape 2 — Nouveau service Web**
1. Dashboard → **New +** → **Web Service**
2. Connectez votre compte GitHub et sélectionnez votre dépôt
3. Configuration :
   - **Name :** `traiteur-agent`
   - **Region :** Frankfurt EU (Central) — important pour la RGPD
   - **Branch :** `main`
   - **Runtime :** Docker
   - **Dockerfile Path :** `etape_02_vocal_agent_prod_rgpd/Dockerfile`
   - **Docker Context Directory :** `etape_02_vocal_agent_prod_rgpd/`
   - **Instance Type :** Free

> Ne cliquez pas encore sur **Create Web Service** — ajoutez d'abord les variables d'environnement ci-dessous.

---

### 3.2 Configurer les variables d'environnement

Dans l'interface de création du service, section **Environment Variables** :

| Variable | Valeur | Note |
|---|---|---|
| `GROQ_API_KEY` | votre clé API Groq | Obligatoire |
| `LLM_PROVIDER` | `groq` | Obligatoire |
| `STT_PROVIDER` | `groq` | Obligatoire |
| `LLM_MODEL` | `llama-3.1-8b-instant` | Obligatoire |
| `STT_MODEL` | `whisper-large-v3-turbo` | Obligatoire |
| `DEBUG_LOCAL` | `false` | **Critique** — ne jamais passer `true` en prod |
| `SECRET_KEY` | *(chaîne aléatoire)* | Recommandé |

**Générer un `SECRET_KEY` :**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Note :** Le service TTS local (Kokoro) ne peut pas tourner sur une instance gratuite Render (512 MB RAM insuffisante). L'agent fonctionnera sans synthèse vocale : les réponses seront textuelles uniquement. C'est acceptable pour une démo ou un test.

Cliquez ensuite sur **Create Web Service** et attendez la fin du premier build (~3-5 minutes).

> **Cold start sur l'instance Free :** Render met le service en veille après 15 minutes d'inactivité. Le premier appel après une période d'inactivité déclenche un démarrage à froid (~30-60 secondes) avant que l'agent réponde. C'est normal et attendu sur le tier gratuit — ne pas interpréter comme un échec de déploiement.

**Questions :**
1. Pourquoi `DEBUG_LOCAL=false` est-il critique en production ? Quelles données seraient exposées si vous mettiez `true` ?
2. Pourquoi le service TTS local ne peut-il pas fonctionner sur un cloud mutualisé (indice : architecture Docker Compose) ?
3. Quelle région Render choisir pour un service destiné à des utilisateurs en France, et pourquoi (indice : principe de minimisation des transferts de données, RGPD art. 44-49) ?
4. La variable `SECRET_KEY` n'est pas encore utilisée dans le code. Pourquoi est-il quand même bonne pratique de la définir maintenant ?

---

### 3.3 Smoke test : vérifier le déploiement

**Test 1 — Health check :**
```bash
curl https://votre-app.onrender.com/health
```

Résultat attendu : `{"status": "ok", "service": "agent"}`

**Test 2 — Appel à l'agent :**
```bash
python tests/tp03_a_appel_agent.py "Bonjour" \
    --url https://votre-app.onrender.com --timing
```

**Test 3 — Golden set contre la production :**

Créez un fichier de configuration dédié `tests/promptfoo-prod.yaml` (ne modifiez pas `promptfoo.yaml` pour éviter un commit accidentel vers la prod) :

```bash
# Copier le fichier et remplacer l'URL
sed 's|http://localhost:8000|https://votre-app.onrender.com|g' \
    tests/promptfoo.yaml > tests/promptfoo-prod.yaml

npx promptfoo@latest eval --config tests/promptfoo-prod.yaml --no-cache \
    --output tests/results/results-prod-v1.0.0.json

# Supprimer le fichier temporaire une fois le test terminé
rm tests/promptfoo-prod.yaml
```

**Test 4 — Comparer prod vs local :**
```bash
python tests/tp03_c_compare.py \
    tests/results/results-v1.6.0-8b.json \
    tests/results/results-prod-v1.0.0.json
```

**Questions :**
1. Le score du golden set en production est-il identique au score local ? Si non, quelles différences observez-vous et comment les expliquer ?
2. La latence en production est-elle différente de celle en local ? Mesurez avec `--timing`.
3. L'endpoint `/api/orders` est-il accessible sans authentification en production ? Est-ce acceptable (rappel : TP 03 partie 4.4) ?
4. Si l'agent ne démarre pas (health check échoue), où consulter les logs sur Render ?

---

## Partie 4 — Déploiement automatique depuis le pipeline (30min)

### 4.1 Créer un Deploy Hook Render

Un **Deploy Hook** est une URL secrète : appeler cette URL en HTTP POST déclenche un redéploiement du service. Elle peut être appelée depuis n'importe où, y compris depuis GitHub Actions.

**Sur Render :** Settings de votre service → **Deploy Hooks** → **Create Deploy Hook**

Nommez-le `github-actions` et copiez l'URL générée (format : `https://api.render.com/deploy/srv-xxx?key=yyy`).

**Ajoutez-la comme secret GitHub :**
- Settings → Secrets and variables → Actions → New repository secret
- **Name :** `RENDER_DEPLOY_HOOK_URL`
- **Value :** l'URL copiée

---

### 4.2 Ajouter le job `deploy` au workflow

Ouvrez `.github/workflows/release.yml` et ajoutez ce job à la fin du fichier :

```yaml
  # ── 7. Déploiement Render.com (sur tag v*.*.*) ──────────────────────────────
  deploy:
    name: Déploiement Render.com
    runs-on: ubuntu-latest
    needs: [unit-tests, docker-build]
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - name: Déclencher le redéploiement
        run: |
          response=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}")
          echo "Render response: $response"
          if [ "$response" != "200" ] && [ "$response" != "201" ]; then
            echo "Échec du déclenchement (HTTP $response)"
            exit 1
          fi
          echo "Déploiement déclenché sur Render.com"
```

> **Attention :** Respectez l'indentation YAML — ce job doit être au même niveau que les autres jobs dans la section `jobs:`.

---

### 4.3 Pipeline complet : du commit au déploiement

Commitez la modification du workflow sur une branche, mergez via PR (si `main` est protégé), puis créez le tag sur le commit résultant :

```bash
# Si main est protégé (section 1.3 configurée)
git checkout -b ci/deploy-render
git add .github/workflows/release.yml
git commit -m "ci: ajout du job de déploiement Render"
git push origin ci/deploy-render
# → Créez la PR sur GitHub, attendez que CI passe, mergez
git checkout main && git pull origin main
```

```bash
# Si main n'est pas protégé (dépôt solo sans protection activée)
git add .github/workflows/release.yml
git commit -m "ci: ajout du job de déploiement Render"
git push origin main
```

Dans les deux cas, taguez ensuite le commit sur `main` :

```bash
git tag -a v1.0.2 -m "Release v1.0.2 - déploiement automatique Render"
git push origin v1.0.2
```

> **Note :** le tag et le push de main sont **deux opérations séparées**. Le pipeline se déclenche sur le push du tag, pas sur le push de la branche.

Observez la progression dans l'onglet **Actions**, puis vérifiez que Render redémarre bien le service.

> **Render déploie depuis les sources, pas depuis GHCR.** Le job `docker-release` publie une image sur GitHub Container Registry pour d'autres usages (déploiement sur un autre cloud, partage d'image). Render, lui, rebuild l'image directement depuis votre `Dockerfile` à chaque déclenchement du hook — les deux sont indépendants.

**Questions :**
1. Combien de temps s'écoule-t-il entre le push du tag et la mise à jour de l'application en production ?
2. Le job `deploy` attend uniquement `unit-tests` et `docker-build`. Quel risque cela représente-t-il ? Comment l'améliorer ?
3. Si le déploiement Render échoue après un tag, comment revenir à la version précédente (rollback) ?
4. *(Bonus)* Modifiez `needs:` du job `deploy` pour qu'il attende également `prompt-tests`. Quel avantage cela apporte-t-il, et quel inconvénient potentiel ?

---

## Rendu attendu

- [ ] Tag `v1.0.0` créé et poussé, pipeline CI/CD déclenché et vert dans GitHub Actions
- [ ] Secret `GROQ_API_KEY` configuré dans les secrets GitHub du dépôt
- [ ] Service déployé sur Render.com, accessible via HTTPS
- [ ] Smoke test `/health` et appel agent réussis en production
- [ ] Job `deploy` ajouté au workflow, déclenché automatiquement sur le tag `v1.0.2`
- [ ] Score golden set en production ≥ 90 %
- [ ] *(Bonus)* Job `deploy` bloqué si `prompt-tests` < 90 % (`needs: [unit-tests, docker-build, prompt-tests]`)
