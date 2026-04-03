# Étape 05 — Quality Gates : Tests automatisés avant l'Atomic Swap

> **Prérequis :** avoir complété l'étape 04 (hot RAG reload disponible).
>
> **Concepts clés :**
> - *"En production, un rebuild sans erreur n'est pas forcément un bon rebuild."*
> - Quality Gate : bloquer une mise en production si la qualité ne satisfait pas un seuil
> - Shift Left : détecter les régressions le plus tôt possible, avant les utilisateurs
> - Tests d'intégration : tester le système complet, pas les composants isolément

---

## Problème posé

Avec l'étape 04, le shadow indexing évite le downtime. Mais il ne garantit pas
la **qualité** du nouvel index :

```bash
# Scénario : data/menus.txt est écrasé par un fichier vide (erreur ops)
echo "" > data/menus.txt

# L'étape 04 rebuild sans erreur...
make rag-rebuild
# → {"status": "started"}   ← pas d'erreur !

# ...mais l'index est maintenant vide
make rag-status
# → {"state": "done", "chunks_active": 3}  ← seulement 3 chunks (horaires seuls !)

# Conséquence : l'agent ne sait plus répondre sur les menus
curl -X POST http://localhost:8000/api/text \
  -d '{"text": "Quel est le prix du bœuf bourguignon ?", "skip_tts": true}'
# → "Je n'ai pas cette information."  ← régression silencieuse en production !
```

**En production, c'est catastrophique** : l'agent dégrade sans alerte, les clients
sont frustrés, et l'équipe ne détecte le problème qu'après plusieurs minutes de logs.

---

## Solution : Quality Gate avant le Swap

```
Étape 04 :
  shadow build (30-60s)
        ↓
  atomic swap ← toujours
        ↓
  nouveau index actif

Étape 05 :
  shadow build (30-60s)
        ↓
  quality gate check (< 5s)   ← NOUVEAU
     hit_rate >= 80% ?
       ↓ oui          ↓ non
  atomic swap     swap annulé
       ↓               ↓
  nouveau index   ancien index conservé
  actif           state = "quality_gate_failed"
```

La quality gate interroge le shadow collection sur 15 requêtes de référence
(`eval/rag_quality_eval.json`) et calcule le **hit rate** :

```
hit_rate = requêtes avec ≥ 1 chunk retourné / total requêtes
```

Si `hit_rate < 80%` → le swap est annulé, l'ancien index reste actif.

---

## Ce qu'on ajoute dans cette étape

| Étape 04 | Étape 05 (nouveau) |
|---|---|
| Rebuild sans vérification qualité | Quality gate avant chaque swap |
| state: idle/rebuilding/done/error | + state: `quality_gate_failed` |
| Swap toujours exécuté si rebuild OK | Swap annulé si hit_rate < 80% |
| Pas de tests automatisés | `tests/` : 3 fichiers pytest |
| Pas de `GET /api/rag/search` | Endpoint de recherche brute (sans LLM) |

### Nouveaux fichiers

```
etape_05_quality_gates/
├── eval/
│   └── rag_quality_eval.json     ← 15 requêtes de référence
├── tests/
│   ├── conftest.py               ← fixtures pytest (BASE_URL, client)
│   ├── test_smoke.py             ← tests rapides sans LLM (< 5s)
│   ├── test_api.py               ← tests d'intégration API (avec LLM)
│   └── test_rag_quality.py       ← quality gate en pytest
└── requirements-test.txt         ← pytest + httpx
```

### Fichiers modifiés vs étape 04

| Fichier | Modification |
|---|---|
| `rag/retriever.py` | + `_check_quality_gate()` dans `_rebuild_worker()` avant `_atomic_swap()` |
| `rag/retriever.py` | + `search_chunks()` — recherche brute sans LLM |
| `app/metrics.py` | + `rag_quality_gate_total` et `rag_quality_gate_hit_rate` |
| `app/main.py` | + `GET /api/rag/search` endpoint |
| `app/config.py` | + `rag_quality_threshold` (0.8), `eval_dir` |
| `docker-compose.yml` | + volume `./eval:/app/eval:ro`, env `EVAL_DIR`, `RAG_QUALITY_THRESHOLD` |
| `Makefile` | + `make test`, `make test-smoke`, `make test-rag`, `make test-api` |

---

## Démarrage

```bash
make init-all
make test-install
```

---

## Démonstration complète

```bash
make rag-demo
```

**Ce que vous verrez :**
1. Avant : question sur les promotions → "Je n'ai pas cette information"
2. Rebuild lancé → retour en < 1ms
3. Pendant le rebuild : requêtes normales continuent
4. Résultat quality gate visible dans `make rag-status`
5. Après : question sur les promotions → réponse avec le contenu de promotions.txt

---

## Tests automatisés

### Lancement rapide (sans Ollama, < 30s)

```bash
# Installe pytest + httpx sur l'hôte
make test-install

# Tests smoke : health, métriques, RAG search
make test-smoke

# Quality gate complète : évalue 15 requêtes
make test-rag
```

### Lancement complet (avec Ollama, 2-3 minutes)

```bash
make test
```

### Organisation des tests

```
tests/
├── test_smoke.py       → Niveau 1 : endpoints répondent-ils ?
│   - /health retourne status=ok
│   - /metrics contient les métriques quality gate
│   - /api/rag/status a le bon schéma
│   - /api/rag/search retourne des chunks
│
├── test_api.py         → Niveau 2 : les contrats API sont-ils respectés ?
│   - POST /api/text retourne tous les champs
│   - Réponse non vide, is_error=False
│   - La réponse sur les horaires contient de vrais horaires (régression RAG)
│
└── test_rag_quality.py → Niveau 3 : quality gate en pytest
    - hit_rate global ≥ 80%
    - Toutes les requêtes "horaires" ont des résultats
    - Hit rate "menus" ≥ 70%
    - Temps de recherche < 2s
```

### Comprendre un échec

```bash
# Exemple de sortie quand la quality gate échoue :
FAILED tests/test_rag_quality.py::TestRagQualityGate::test_global_hit_rate_above_threshold

Hit rate trop bas : 40.0% (6/15 requêtes) < seuil=80%

Requêtes sans résultat (9) :
  - [menus] bœuf bourguignon prix portion
  - [menus] plateau charcuterie personnes prix
  - [menus] formule buffet complet mariage
  ...

→ Ces requêtes n'ont pas de chunk correspondant dans ChromaDB.
→ Vérifiez que les fichiers data/*.txt sont bien indexés.
```

**Actions correctives :**
1. Vérifier que `data/menus.txt` n'est pas vide : `cat data/menus.txt | wc -l`
2. Relancer l'indexation : `make rag-rebuild`
3. Attendre la fin : `make rag-watch`
4. Relancer les tests : `make test-rag`

---

## Workflow manuel pas à pas

```bash
# 1. Recherche brute (sans LLM) — pour debug et tests
make rag-search Q="horaires samedi"
# → {"hits": 2, "chunks": [{"content": "Samedi : 09h00...", "score": 0.12}]}

# 2. Lancer un rebuild avec quality gate
make rag-rebuild
# → {"status": "started", "message": "Rebuild shadow démarré..."}

# 3. Surveiller l'avancement
make rag-watch
# → Polling toutes les 5s...

# 4. Voir le résultat de la quality gate
make rag-status
# → {
#      "state": "done",
#      "quality_gate": {
#        "hit_rate": 0.933,
#        "passed": true,
#        "threshold": 0.8
#      }
#    }

# Ou si la quality gate a échoué :
# → {
#      "state": "quality_gate_failed",
#      "error": "Quality gate FAILED : hit_rate=40.0% (6/15) < seuil=80%. Swap annulé.",
#      "quality_gate": {
#        "hit_rate": 0.4,
#        "passed": false,
#        "threshold": 0.8
#      }
#    }
```

---

## Métriques Grafana (nouvelles)

```promql
# La dernière quality gate a-t-elle passé ?
rag_quality_gate_total{result="passed"}
rag_quality_gate_total{result="failed"}

# Distribution du hit rate lors des quality gates
histogram_quantile(0.5, rate(rag_quality_gate_hit_rate_bucket[1h]))

# Alerte : trop de quality gate failures
rate(rag_quality_gate_total{result="failed"}[1h]) > 0
```

---

## Configurer le seuil

Le seuil est configurable via variable d'environnement :

```bash
# docker-compose.yml ou .env
RAG_QUALITY_THRESHOLD=0.9   # 90% minimum (plus strict)
RAG_QUALITY_THRESHOLD=0.6   # 60% minimum (plus permissif)
RAG_QUALITY_THRESHOLD=0.0   # Désactive la gate (toujours passe)
```

---

## Concept : Shift Left

```
← détection plus tôt                         détection plus tard →

[tests unitaires]  [quality gate]  [staging]  [canary]  [production]  [monitoring]
      ↑                  ↑              ↑          ↑           ↑             ↑
   < 1ms               < 5s          minutes    heures      jours        semaines
   coût faible        coût faible   coût moyen  coût élevé  coût élevé  coût très élevé
```

**Pourquoi "shift left" ?**
- Chaque problème détecté en production coûte plus cher qu'en développement
- La quality gate détecte les régressions RAG **avant** qu'un utilisateur les subisse
- La quality gate s'exécute automatiquement à chaque rebuild → pas d'oubli humain

**Analogies dans d'autres domaines :**

| Domaine | Quality Gate équivalent |
|---|---|
| Kubernetes Deployment | Readiness probe avant basculement du trafic |
| Elasticsearch | Index validation avant alias swap |
| ML Model | Accuracy check avant mise en production |
| CI/CD | Tests automatisés avant merge en main |

---

## Commandes utiles

```bash
make up               # Démarre tous les services
make init-all         # Build + up + Mistral (première installation)

make test-install     # Installe pytest + httpx sur l'hôte
make test-smoke       # Tests rapides sans LLM (< 30s) ← commencer ici
make test-rag         # Quality gate complète (< 30s, sans LLM)
make test-api         # Tests complets avec LLM (2-3min)
make test             # Tous les tests

make rag-rebuild      # Lance un rebuild + quality gate
make rag-status       # État courant + résultat quality gate
make rag-watch        # Polling jusqu'à la fin
make rag-rollback     # Revient à la collection précédente
make rag-search Q="…" # Recherche brute sans LLM
make rag-demo         # Démonstration guidée complète
```

---

## Ce que prépare cette étape

```
Étape 06 → Staging vs Production
  Problème : comment tester un changement d'infrastructure AVANT la production ?
  Solution : deux Docker Compose (staging.yml, production.yml),
             variables d'environnement différentes (data de test vs data réelle),
             promouvoir staging → production via make promote.
  Concepts : environnements, promotion d'artefacts, infrastructure as code.
```
