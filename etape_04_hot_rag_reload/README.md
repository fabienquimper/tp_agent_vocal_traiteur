# Étape 04 — Hot RAG Reload : Shadow Indexing + Atomic Pointer Swap

> **Prérequis :** avoir complété l'étape 02 (métriques disponibles).
>
> **Concepts clés :**
> - *"En production, personne ne peut se permettre 30 secondes de downtime pour changer un fichier de données."*
> - Shadow indexing : construire en parallèle, sans toucher à la production
> - Atomic pointer swap : basculer en une instruction, sans état intermédiaire

---

## Problème posé

Ajoutez `data/promotions.txt` au traiteur. Avec l'étape 03, voici ce qui se passe :

```bash
# Étape 03 : reload BLOQUANT
curl -X POST http://localhost:8000/api/reload-documents
# → Attente 30-60s
# → Pendant ce temps : toutes les requêtes RAG échouent ou retournent l'ancien index
```

**En production, c'est inacceptable** :
- 60 secondes de downtime pour chaque mise à jour de la carte des menus
- Si le rebuild plante à mi-chemin, l'index est corrompu

---

## Solution : Shadow Indexing + Atomic Swap

```
Avant (étape 03) :
  ┌─────────────┐   reload   ┌──────────────────┐
  │ vectorstore │ ─────────▶ │  (vide / erreur) │  ← downtime !
  │  "langchain"│            └──────────────────┘
  └─────────────┘

Après (étape 04) :
  ┌───────────────────┐
  │ vectorstore ACTIF │ ─── sert les requêtes normalement
  │  "traiteur_1000"  │
  └───────────────────┘
          ↑
          │ atomic swap (< 1µs)
          │
  ┌───────────────────┐
  │ vectorstore SHADOW│ ─── construit en background (30-60s)
  │  "traiteur_1060"  │     l'agent ne l'utilise pas encore
  └───────────────────┘
```

---

## Ce qu'on ajoute dans cette étape

| Étape 03 | Étape 04 (nouveau) |
|---|---|
| `/api/reload-documents` bloquant (30s+) | Non-bloquant, retourne en < 1ms |
| Une seule collection ChromaDB | Collections nommées avec timestamp |
| Downtime pendant le rebuild | Zéro downtime, rollback disponible |
| Pas de suivi de progression | `GET /api/rag/status` + métriques Grafana |

### Nouveaux fichiers

```
etape_04_hot_rag_reload/
├── data/
│   └── promotions.txt          ← nouveau fichier pour démontrer le hot reload
└── services/agent/app/
    └── rag/
        └── retriever.py        ← RÉÉCRIT : shadow indexing + atomic swap
```

### Fichiers modifiés vs étape 03

| Fichier | Modification |
|---|---|
| `rag/retriever.py` | Complet : shadow indexing, atomic swap, rollback, status |
| `app/metrics.py` | + `rag_rebuild_*` métriques |
| `app/main.py` | + endpoints `/api/rag/rebuild`, `/api/rag/status`, `/api/rag/rollback` |
| `Makefile` | + `make rag-rebuild`, `rag-status`, `rag-watch`, `rag-rollback`, `rag-demo` |

---

## Démarrage

```bash
make init-all
```

---

## Démonstration complète

```bash
# Démonstration guidée en une commande
make rag-demo
```

**Ce que vous verrez :**

1. **Avant** : question sur les promotions → "Je n'ai pas cette information" (promotions.txt pas encore indexé)
2. **Lancement du rebuild** → retourne en < 1ms : `{"status": "started"}`
3. **Pendant** : les requêtes continuent de fonctionner (ancien index actif)
4. **Après** : question sur les promotions → répond avec le contenu de `data/promotions.txt`

### Workflow manuel pas à pas

```bash
# 1. Question sur les promotions (promotions.txt PAS encore dans l'index initial)
curl -X POST http://localhost:8000/api/text \
  -d '{"text": "Avez-vous des promotions ?", "skip_tts": true}'
# → "Je n'ai pas cette information."

# 2. Déclencher le rebuild (non-bloquant)
make rag-rebuild
# → {"status": "started", "message": "Rebuild shadow démarré en arrière-plan..."}
# → Retour IMMÉDIAT

# 3. Pendant le rebuild, les requêtes fonctionnent toujours
curl -X POST http://localhost:8000/api/text \
  -d '{"text": "Quels sont vos horaires ?", "skip_tts": true}'
# → Répond normalement (ancienne collection encore active)

# 4. Suivre l'avancement
make rag-status
# → {"state": "rebuilding", "active_collection": "traiteur_1000", "elapsed_s": 12.4}

# 5. Attendre la fin
make rag-watch
# → Polling toutes les 5s jusqu'à state=done

# 6. Vérifier le résultat
make rag-status
# → {"state": "done", "active_collection": "traiteur_1060", "chunks_active": 87,
#    "duration_s": 34.2, "rollback_available": true}

# 7. Question sur les promotions (APRÈS le rebuild)
curl -X POST http://localhost:8000/api/text \
  -d '{"text": "Avez-vous des promotions ?", "skip_tts": true}'
# → "Oui ! Nous avons une formule Fête des mères avec -10€..."

# 8. Si le nouveau index dégrade la qualité : rollback instantané
make rag-rollback
# → {"status": "ok", "message": "Rollback effectué → collection 'traiteur_1000'"}
```

---

## Concepts clés

### Shadow Indexing

Construire le nouvel index **sans toucher à l'ancien** :

```
Production :   [traiteur_1000] ─── sert 100% des requêtes
Shadow :       [traiteur_1060] ─── construction en cours (0% des requêtes)

Swap :         [traiteur_1000] ─── 0% des requêtes (gardé en mémoire)
               [traiteur_1060] ─── sert 100% des requêtes

Rollback :     [traiteur_1000] ─── sert 100% des requêtes (si besoin)
```

### Atomic Pointer Swap et le GIL Python

```python
# Cette ligne est atomique en CPython (GIL = Global Interpreter Lock)
_vectorstore = new_vectorstore

# Pourquoi ?
# CPython compile cette ligne en un seul opcode : STORE_GLOBAL
# Le GIL garantit qu'un seul thread exécute du bytecode à la fois
# → aucun thread ne peut lire _vectorstore pendant cette instruction
# → impossible de voir un état intermédiaire

# Ce que voit chaque thread concurrent :
#   - Avant le swap : l'ancien vectorstore complet
#   - Après le swap : le nouveau vectorstore complet
#   - JAMAIS : "ni l'un ni l'autre" ou "les deux à la fois"
```

**Analogies en production :**

| Technologie | Mécanisme équivalent |
|---|---|
| Python `_ptr = new_obj` | GIL rend l'assignment atomique |
| Redis `RENAME key tmpkey` | Atomic key swap |
| Elasticsearch | Alias swap (`POST /_aliases`) |
| PostgreSQL | `ALTER TABLE ... RENAME` |
| Kubernetes | Deployment rolling update |

### Persistance entre redémarrages

Le nom de la collection active est sauvegardé dans `chroma/rag_metadata.json` :

```json
{
  "active": "traiteur_1714500060",
  "prev": "traiteur_1714500000"
}
```

Au redémarrage, l'agent charge la bonne collection. Sans ce fichier, il
rechargerait toujours la première collection créée (comportement étape 03).

### Métriques Grafana (nouvelles)

Quatre nouvelles métriques ajoutées à `metrics.py` :

```promql
# Y a-t-il un rebuild en cours ? (1 = oui, 0 = non)
rag_rebuild_in_progress

# Nombre de chunks dans la collection active
rag_active_chunks

# Durée des rebuilds P50/P95
histogram_quantile(0.95, rate(rag_rebuild_duration_seconds_bucket[1h]))

# Taux de succès des rebuilds
rate(rag_rebuild_total{status="success"}[1h])
```

---

## Nouveaux endpoints API

### `POST /api/rag/rebuild`

```bash
curl -X POST http://localhost:8000/api/rag/rebuild
# Retour immédiat (< 1ms) :
{
  "status": "started",
  "message": "Rebuild shadow démarré en arrière-plan..."
}

# Si un rebuild est déjà en cours :
{
  "status": "already_running",
  "message": "Un rebuild est déjà en cours.",
  "rag": {"state": "rebuilding", "elapsed_s": 18.3}
}
```

### `GET /api/rag/status`

```bash
# Pendant le rebuild
{"state": "rebuilding", "active_collection": "traiteur_1000", "elapsed_s": 22.1}

# Après le rebuild
{
  "state": "done",
  "active_collection": "traiteur_1060",
  "previous_collection": "traiteur_1000",
  "chunks_active": 87,
  "duration_s": 34.2,
  "rollback_available": true
}

# En cas d'erreur
{"state": "error", "error": "...message d'erreur..."}
```

### `POST /api/rag/rollback`

```bash
curl -X POST http://localhost:8000/api/rag/rollback
{
  "status": "ok",
  "message": "Rollback effectué → collection 'traiteur_1000'",
  "rag": {"state": "idle", "chunks_active": 72, "rollback_available": false}
}
```

---

## Commandes utiles

```bash
make up               # Démarre tous les services
make rag-demo         # Démonstration complète (recommandé pour le TP)

make rag-rebuild      # Lance un rebuild non-bloquant
make rag-status       # État courant du RAG
make rag-watch        # Polling jusqu'à la fin du rebuild
make rag-rollback     # Revient à la collection précédente

# Blue/Green STT (hérités de l'étape 03)
make stt-switch-green
make stt-switch-blue

# Benchmark STT (hérité de l'étape 03)
make benchmark-stt
```

---

## Ce que prépare cette étape

```
Étape 05 → Tests automatisés + Quality Gates
  Problème : comment garantir que le nouveau index RAG améliore (ou ne dégrade pas)
             la qualité des réponses AVANT de valider le swap ?
  Solution : exécuter une suite de tests automatisés après le rebuild,
             valider un score minimum (ex: hit rate > 80%, WER < 10%),
             bloquer le swap si les tests échouent.
  Concepts : pytest, quality gates, CI pipeline, "shift left".
```
