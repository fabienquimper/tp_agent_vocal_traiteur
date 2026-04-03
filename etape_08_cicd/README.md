# Étape 08 — CI/CD : GitHub Actions, Tests Unitaires, Sécurité

> **Prérequis :** avoir complété l'étape 07. Un compte GitHub (gratuit suffit).
>
> **Concepts clés :**
> - *"Le code non testé automatiquement est du code qui se casse en production."*
> - CI (Continuous Integration) : vérifier automatiquement chaque commit
> - CD (Continuous Deployment) : déployer automatiquement après validation
> - "Shift left" : détecter les problèmes le plus tôt possible
> - Tests unitaires vs tests d'intégration : vitesse vs réalisme

---

## Problème posé

Avec les étapes précédentes, chaque déploiement est **manuel** :

```
Développeur écrit du code
      ↓
Développeur oublie de lancer les tests
      ↓  (ou les lance, mais seulement smoke tests)
git push → déploiement manuel
      ↓
Bug en production 🔥
      ↓
"Mais ça marchait sur ma machine !"
```

Autre problème : un Dockerfile cassé ou une dépendance avec une CVE critique
peut passer inaperçu si personne ne vérifie systématiquement.

---

## Solution : Pipeline CI/CD

```
git push
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│  Pipeline CI (GitHub Actions)                           │
│                                                         │
│  1. Lint (30s)      → syntaxe + imports corrects ?      │
│         ↓ OK                                            │
│  2. Unit Tests (60s) → logique métier correcte ?        │
│         ↓ OK                                            │
│  3. Docker Build (5min) → images buildables ?           │
│         ↓ OK                                            │
│  4. Security (3min) → pas de CVE critiques ?            │
│         ↓ OK                                            │
└─────────────────────────────────────────────────────────┘
         │
         ▼ (sur push main uniquement)
┌─────────────────────────────────────────────────────────┐
│  Pipeline CD (GitHub Actions)                           │
│                                                         │
│  5. kind cluster éphémère                               │
│  6. Deploy (mock-ollama + agent + stt + tts + ui)       │
│  7. Smoke tests + RAG quality gate                      │
│         ↓ OK → déploiement validé                       │
└─────────────────────────────────────────────────────────┘
```

**Fail fast** : si le lint échoue, on ne lance pas les tests. Si les tests
échouent, on ne build pas. Chaque étape économise du temps CI.

---

## Ce qu'on ajoute dans cette étape

| Étape 07 (Kubernetes) | Étape 08 (CI/CD) |
|---|---|
| Tests lancés manuellement | Tests automatiques à chaque push |
| Lint manuel (ou oublié) | ruff automatique sur chaque PR |
| Vulnérabilités non détectées | Trivy scanne les images en CI |
| Ollama lourd (~4 GB) même en CI | mock-ollama léger (~50 MB) pour les runners |
| Pas de tests unitaires | `test_unit.py` : 20+ tests purs Python |

### Nouveaux fichiers

```
etape_08_cicd/
├── .github/
│   └── workflows/
│       ├── ci.yml           ← Pipeline CI (4 jobs : lint, unit, build, security)
│       └── cd.yml           ← Pipeline CD (kind éphémère + smoke tests)
├── mock-ollama/
│   ├── server.py            ← Serveur HTTP qui simule l'API Ollama (~150 lignes)
│   └── Dockerfile           ← Image ultra-légère (~50 MB vs 4.5 GB)
├── k8s/
│   └── ci/
│       └── mock-ollama.yaml ← Manifeste K8s du mock (remplace ollama.yaml en CI)
├── tests/
│   └── test_unit.py         ← Tests purs Python (sans Docker, < 30s)
├── pyproject.toml           ← Config ruff + pytest
└── scripts/
    └── ci-local.sh          ← Simule le CI en local
```

---

## Démarrage rapide (local)

```bash
# 1. Tests unitaires — sans aucun service (< 30s)
make test-unit

# 2. Lint du code Python
make lint

# 3. Simuler le pipeline CI complet en local
make ci-local
```

---

## Pipeline CI en détail

### Job 1 : Lint (ruff)

```bash
# Ce que GitHub Actions exécute :
ruff check services/agent/app/ tests/test_unit.py
ruff format --check services/agent/app/ tests/test_unit.py
```

**ruff** est un linter Python écrit en Rust, ~100x plus rapide que flake8.
Il vérifie : erreurs de syntaxe, imports non utilisés, variables non définies,
ordre des imports (isort), formatage.

```bash
# En local : corriger automatiquement
make lint-fix
```

### Job 2 : Tests unitaires

```bash
# tests/test_unit.py — 3 classes de tests :
python3 -m pytest tests/test_unit.py -v
```

Ces tests **n'ont besoin d'aucun service Docker** :

| Classe | Ce qui est testé |
|---|---|
| `TestDetectPaymentMethod` | Reconnaissance CB/liquide depuis texte libre |
| `TestExtractPhone` | Extraction regex numéros français (+33, 06, etc.) |
| `TestSettingsDefaults` | Valeurs par défaut + override par variables d'env |

```bash
# Exemple d'output :
# tests/test_unit.py::TestDetectPaymentMethod::test_cb_keyword PASSED
# tests/test_unit.py::TestDetectPaymentMethod::test_carte_keyword PASSED
# ...
# 20 passed in 0.8s
```

**Pourquoi ces fonctions ?** `_detect_payment_method` et `_extract_phone` sont
des fonctions métier pures (pas d'I/O, pas de réseau) — les plus simples à
tester unitairement, et les plus susceptibles de régressions si quelqu'un
modifie la logique de reconnaissance.

### Job 3 : Docker Build

Valide que tous les Dockerfiles compilent. N'exécute pas les conteneurs.
Utilise le cache GitHub Actions (`cache-from: type=gha`) pour accélérer
les builds successifs.

### Job 4 : Security (Trivy)

```
Trivy scanne :
  1. L'image traiteur-agent:ci → CVE dans l'OS de base + bibliothèques Python
  2. Le filesystem services/agent/ → dépendances dans requirements.txt

Mode : CRITICAL + HIGH seulement → bloquant
        MEDIUM + LOW → ignoré (trop de bruit, fixes trop complexes)
```

---

## Pipeline CD en détail

### Pourquoi mock-ollama ?

Les runners GitHub Actions ont **~7 GB de RAM**. Notre stack complète :
- Ollama + Mistral 7B : ~4.5 GB
- ChromaDB + agent : ~512 MB
- STT (Whisper base) : ~600 MB
- TTS (Piper) : ~200 MB
- **Total production : ~6+ GB** → trop juste, risque d'OOM

Solution : remplacer Ollama par un mock Python ultra-léger.

```python
# mock-ollama/server.py — ~150 lignes, bibliothèque standard uniquement
# Répond à :
#   GET  /api/tags      → liste "mistral" comme modèle disponible
#   POST /api/chat      → réponse statique cohérente (streaming NDJSON)
#   POST /api/generate  → idem
```

```
Production : ollama/ollama:latest → 4.5 GB, démarrage ~60s
CI         : mock-ollama:ci      → ~50 MB,  démarrage ~1s
```

Les tests qui s'exécutent en CD (`test_smoke.py`, `test_rag_quality.py`)
**ne font pas d'appels LLM** — ils testent l'infrastructure (health, métriques,
ChromaDB). Le mock n'est là que pour que l'agent démarre sans erreur.

### Déploiement K8s en CI

```yaml
# cd.yml — logique de déploiement
# 1. kind cluster éphémère (helm/kind-action)
# 2. Build + kind load de toutes les images (dont mock-ollama)
# 3. kubectl apply k8s/ci/mock-ollama.yaml  → Deployment "ollama" = mock
# 4. kubectl apply k8s/*.yaml (sauf ollama.yaml)
# 5. Port-forward agent → localhost:8000
# 6. pytest tests/test_smoke.py tests/test_rag_quality.py
```

Le cluster kind est **éphémère** : créé au début du job, détruit à la fin.
Chaque run CI part d'un état propre.

---

## Démonstrations

### 1. Voir le pipeline en action

```bash
# Pousser un commit sur main déclenche CI + CD
git add -A && git commit -m "test ci" && git push

# Voir l'état des pipelines
gh run list

# Voir les logs d'un run
gh run view <run-id> --log
```

### 2. Simuler le CI en local

```bash
# Job 1 : lint
make lint

# Job 2 : tests unitaires
make test-unit

# Job 3 : docker build
make ci-local build

# Job 4 : sécurité (nécessite trivy installé)
make ci-local security

# Tout d'un coup
make ci-local
```

### 3. Comprendre la différence CI vs intégration

```bash
# Tests unitaires — 0 service requis, < 30s
make test-unit

# Tests d'intégration — nécessitent le cluster K8s
make k8s-up
make test-smoke      # health + métriques + RAG search
make test-rag        # quality gate RAG (ChromaDB)
```

### 4. Tester le mock-ollama

```bash
# Lancer le mock localement
docker run --rm -p 11434:11434 mock-ollama:ci &

# Vérifier qu'il simule Ollama
curl http://localhost:11434/api/tags
# → {"models": [{"name": "mistral", ...}]}

curl -s http://localhost:11434/api/chat \
  -d '{"model":"mistral","messages":[{"role":"user","content":"Bonjour"}],"stream":false}'
# → {"message":{"role":"assistant","content":"Bonjour ! Je suis l'assistant..."}}
```

---

## Architecture CI/CD

```
GitHub Repository
       │
       │  git push
       ▼
┌──────────────────────────────────────────────────────┐
│  GitHub Actions                                      │
│                                                      │
│  CI workflow (ci.yml) :                              │
│    lint → unit-tests → docker-build → security       │
│                    ↓ tous OK                         │
│  CD workflow (cd.yml) :                              │
│    ┌─────────────────────────────────────────┐       │
│    │  Runner Ubuntu (7 GB RAM)               │       │
│    │                                         │       │
│    │  kind cluster "traiteur" (éphémère)     │       │
│    │  ┌────────────────────────────────────┐ │       │
│    │  │ mock-ollama (~50 MB)               │ │       │
│    │  │ traiteur-agent (2 replicas)        │ │       │
│    │  │ traiteur-stt (Whisper base)        │ │       │
│    │  │ traiteur-tts (Piper)               │ │       │
│    │  └────────────────────────────────────┘ │       │
│    │         ↓                               │       │
│    │  pytest smoke + RAG quality tests       │       │
│    │         ↓ OK                            │       │
│    │  ✓ Déploiement validé                   │       │
│    └─────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────┘
```

---

## Commandes utiles

```bash
# ── CI local ──────────────────────────────────────────────────────────────
make lint              # lint du code Python
make lint-fix          # correction automatique du style
make test-unit         # tests unitaires (sans Docker)
make ci-local          # simulation complète du CI

# ── K8s (hérité étape 07) ─────────────────────────────────────────────────
make k8s-up            # cluster + build + deploy
make k8s-init-ollama   # télécharge Mistral (~4 GB)
make k8s-status        # état des pods/services/HPA

# ── Tests d'intégration (nécessitent le cluster) ──────────────────────────
make test-smoke        # health + métriques + RAG search
make test-rag          # quality gate RAG
make test-api          # contrats API (nécessite Ollama)
make test              # tous les tests

# ── GitHub CLI ────────────────────────────────────────────────────────────
gh run list                    # liste des runs CI/CD
gh run view <id> --log         # logs d'un run
gh run watch                   # surveiller le run en cours
```

---

## Ce que prépare cette étape

```
Étape 09 → GitOps avec ArgoCD
  Problème : le CD actuel "push" le déploiement depuis CI.
             En production, on préfère que le cluster "pull" l'état désiré
             depuis Git (source of truth).
  Solution : ArgoCD surveille le dépôt Git et synchronise le cluster.
  Concepts : GitOps, reconciliation loop, declarative state.
```
