# Étape 06 — Staging vs Production : Deux environnements isolés

> **Prérequis :** avoir complété l'étape 05 (quality gates disponibles).
>
> **Concepts clés :**
> - *"On ne teste pas en production."*
> - Staging : un miroir de production avec des données de test, où tout peut casser
> - Infrastructure as Code : deux compose-files → deux environnements reproductibles
> - Promotion : un workflow contrôlé pour passer de staging à production

---

## Problème posé

Avec l'étape 05, on peut tester la qualité du RAG avant un swap. Mais comment
tester un changement de données **avant même de le mettre en production** ?

```bash
# Scénario : ajouter de nouvelles formules au menu
# Étape 05 : modifier data/menus.txt directement...

vim data/menus.txt   # ← modifications en live sur la production !
make rag-rebuild     # ← si ça rate, c'est la production qui est impactée
                     # ← si les données sont mal formatées, la quality gate
                     #    peut refuser, mais les fichiers sont déjà modifiés

# Problème : on travaille DIRECTEMENT sur les données de production
```

**En production, c'est risqué** : une erreur de frappe dans `data/menus.txt`,
un fichier mal encodé, ou une erreur de format peuvent dégrader la production
pendant la fenêtre entre la modification et le rebuild.

---

## Solution : Environnement Staging

```
Avant (étape 05) :
  données → data/ → production directement

Après (étape 06) :
  données → data-staging/ → agent-staging:8100 → tests → make promote → data/ → production:8000
```

Staging est une instance **séparée** de l'agent qui :
- Utilise `data-staging/` (données de test, avec marqueurs)
- Tourne sur le port **8100** (production reste sur 8000)
- Partage ollama, stt, tts avec la production (services lourds non dupliqués)
- A son propre index ChromaDB (`chroma_staging`)

---

## Ce qu'on ajoute dans cette étape

| Étape 05 | Étape 06 (nouveau) |
|---|---|
| Un seul environnement | Production + Staging en parallèle |
| Données modifiées en live | `data-staging/` isolé de `data/` |
| Pas de workflow de promotion | `make promote` (tests + copie + rebuild) |
| APP_ENV absent | `GET /health` révèle `"env": "staging"` ou `"production"` |

### Nouveaux fichiers

```
etape_06_staging_production/
├── docker-compose.staging.yml    ← ajoute le service agent-staging (port 8100)
├── data-staging/                 ← données de test (avec marqueurs staging)
│   ├── menus.txt                 ← copie production + "Assiette Démo Staging"
│   ├── promotions.txt            ← copie production + "STAGING_PROMO_TEST_2025"
│   ├── horaires.txt              ← identique à production
│   └── conges.txt                ← identique à production
├── orders-staging/               ← commandes isolées du staging
└── scripts/
    └── promote.sh                ← workflow de promotion (tests + copie + rebuild)
```

### Fichiers modifiés vs étape 05

| Fichier | Modification |
|---|---|
| `app/config.py` | + `app_env: str = "production"` |
| `app/main.py` | `/health` retourne `"env": settings.app_env` |
| `tests/test_environments.py` | Nouveau : tests d'isolation staging/production |
| `Makefile` | + `staging-*`, `promote`, `promote-force` |

---

## Démarrage

```bash
# 1. Démarrer la production
make init-all

# 2. Démarrer staging (en parallèle)
make staging-up

# 3. Indexer les données staging
make staging-rebuild && make staging-watch

# 4. Lancer les tests staging
make staging-test
```

---

## Workflow de promotion complet

```bash
# Étape A : Modifier les données staging
vim data-staging/menus.txt   # ← en toute sécurité, production non affectée

# Étape B : Rebuilder l'index staging
make staging-rebuild
make staging-watch           # attendre la fin

# Étape C : Tester staging
make staging-test
# → tests smoke + quality gate + isolation

# Étape D : Si tout est vert → promouvoir
make promote
# → 1. Tests staging relancés automatiquement
# → 2. data-staging/ → data/ (avec sauvegarde)
# → 3. Rebuild production (quality gate incluse)
# → 4. Vérification finale

# Étape E : Validation finale
make test
```

---

## Isolation des environnements

Les données staging contiennent des **marqueurs uniques** :

| Marqueur | Fichier | Rôle |
|---|---|---|
| `Assiette Démo Staging` | `data-staging/menus.txt` | Produit fictif de test |
| `STAGING_PROMO_TEST_2025` | `data-staging/promotions.txt` | Code promo fictif |

**Tests d'isolation (`test_environments.py`) :**
- En staging → les marqueurs DOIVENT être trouvés (sinon données pas indexées)
- En production → les marqueurs NE DOIVENT PAS être trouvés (sinon contamination)

```bash
# Vérifier l'isolation manuellement
make rag-search Q="Assiette Démo Staging"         # → 0 hits en production ✓
make staging-search Q="Assiette Démo Staging"     # → 1+ hits en staging ✓
```

---

## Script de promotion

`scripts/promote.sh` exécute ce workflow en 5 étapes :

```
1. Health checks staging et production
2. Vérification des données staging (marqueur présent dans l'index ?)
3. Tests automatisés sur staging (smoke + quality gate)
         ↓ succès                    ↓ échec
4a. Sauvegarde data/ + copie     4b. Abandon → production inchangée
    data-staging/ → data/
         ↓
5. Rebuild production (quality gate)
    ↓ passed              ↓ failed
    Promotion OK       Rollback auto → data-backup-*/
```

---

## Architecture Docker

```
┌─────────────────────────────────────────────────────────┐
│  docker-compose.yml (production)                        │
│                                                         │
│  ollama ←── agent:8000 ←── data/        ← utilisateurs │
│             stt-router                                  │
│             tts                                         │
│             prometheus + grafana                        │
└─────────────────────────────────────────────────────────┘
         ↑ services partagés (ollama, stt-router, tts)
┌─────────────────────────────────────────────────────────┐
│  docker-compose.staging.yml (overlay)                   │
│                                                         │
│  agent-staging:8100 ←── data-staging/   ← tests        │
│  (partage ollama, stt-router, tts)                      │
└─────────────────────────────────────────────────────────┘
```

**Pourquoi partager les services lourds ?**
- Ollama (LLM) : ~4 GB RAM — trop lourd à dupliquer
- STT (Whisper) : ~1 GB RAM — idem
- TTS (Piper) : ~200 MB RAM — idem
- Seul l'agent est léger (~100 MB) et facile à dupliquer

---

## Commandes utiles

```bash
# Production
make up                # démarre production
make test              # teste production
make rag-rebuild       # rebuild RAG production

# Staging
make staging-up        # démarre staging (production doit tourner)
make staging-rebuild   # rebuild RAG staging
make staging-watch     # attend la fin du rebuild staging
make staging-test      # tests smoke + quality gate + isolation
make staging-logs      # logs de l'agent staging

# Recherche
make rag-search Q="…"          # production
make staging-search Q="…"      # staging

# Promotion
make promote           # promeut staging → production (avec tests)
make promote-force     # promeut sans tests (urgence)

# Démo
make rag-demo          # démo workflow complet staging → production
```

---

## Ce que prépare cette étape

```
Étape 07 → Déploiement Kubernetes local (kind)
  Problème : Docker Compose ne scale pas. Comment gérer 3 instances de l'agent
             derrière un load balancer, avec autoscaling selon la charge ?
  Solution : kind (Kubernetes in Docker), Deployment + Service + HPA
             (Horizontal Pod Autoscaler).
  Concepts : pods, replicas, services, HPA, kubectl, rolling update K8S.
```
