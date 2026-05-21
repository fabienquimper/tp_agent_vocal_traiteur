# Étape 02 – Agent Vocal Traiteur (Production / RGPD)

Agent vocal pour la prise de commandes chez un traiteur.  
Architecture orientée **release applicative** : code + prompts + config modèles + menu versionnés.

---

## Prérequis

- Docker + Docker Compose
- Une clé API Groq gratuite → https://console.groq.com/keys  
  *(ou Mistral, ou Ollama en local — voir section Providers)*

---

## Démarrage rapide

```bash
cp .env.example .env
# Éditer .env : renseigner GROQ_API_KEY (ou autre provider)
docker compose up
```

Ouvrir http://localhost:8000 → **chatbot vocal**  
Ouvrir http://localhost:8000/traiteur.html → tableau de bord commandes

---

## Modes de démarrage

### Mode développement (rechargement à chaud)

`docker-compose.override.yml` est inclus dans le dépôt. Docker Compose le fusionne
automatiquement avec `docker-compose.yml` sans aucune commande spéciale.

```bash
docker compose up          # pas de --build nécessaire
```

Ce que ça apporte :
- `src/` et `ui/` montés en volume → les modifications sont visibles immédiatement
- `uvicorn --reload` → redémarre en ~1 s dès qu'un fichier Python change
- Pas besoin de rebuild entre deux itérations de code

### Mode production (image figée)

Pour construire et tester l'artefact final, comme le ferait la CI :

```bash
docker compose -f docker-compose.yml up --build
```

Le fichier `docker-compose.override.yml` est ignoré. L'image est construite
une seule fois, les fichiers sont copiés dedans. C'est ce comportement qui
est testé en CI/CD.

### Mode 100 % local (sans clé API)

```bash
./scripts/setup_ollama_local.sh   # installe Ollama + pull le modèle
# Dans .env :
#   LLM_PROVIDER=local_ollama
#   STT_PROVIDER=local_ollama
docker compose up
```

Aucune donnée ne quitte la machine.

---

## Providers supportés

| Composant | Providers disponibles |
|-----------|----------------------|
| STT       | `groq` · `local_ollama` (faster-whisper) · `local_lms` |
| LLM       | `groq` · `mistral` · `local_ollama` · `local_lms` |

Configurer dans `.env` :

```env
STT_PROVIDER=groq
LLM_PROVIDER=local_ollama
LLM_MODEL=qwen2.5:7b
```

---

## Tests

```bash
# Tests unitaires (< 2 s, sans réseau)
pytest -m "not slow"

# Tests de prompts — nécessite promptfoo (npm i -g promptfoo) + agent démarré
promptfoo eval --config tests/promptfoo.yaml

# Tests de conversation complets (appels LLM réels, agent démarré)
pytest -m slow
```

---

## Déploiement cloud (étudiants)

Le `docker-compose.yml` suffit pour un déploiement léger.  
Utiliser `LLM_PROVIDER=groq` ou `mistral` (Ollama n'est pas disponible sur les clouds mutualisés).

### Render.com — recommandé pour un TP

1. Créer un compte sur https://render.com (gratuit)
2. *New → Web Service → Deploy an existing image* ou connecter le dépôt GitHub
3. Renseigner les variables d'environnement dans l'interface (onglet *Environment*)  
   → copier les clés du `.env.example`, **ne jamais commiter le `.env`**
4. Ajouter un disque persistant (*Disk*) monté sur `/app/orders` pour conserver les Excel

> Le plan gratuit met le service en veille après 15 min d'inactivité (premier appel lent).  
> Le plan Starter à $7/mois maintient le service actif en permanence.

### Alternatives

| Plateforme | Avantage | Limite gratuite |
|------------|----------|-----------------|
| **Railway** | DX excellent, déploiement en 1 clic | $5 crédit/mois |
| **Fly.io** | Persistance native, edge | 3 VMs partagées |
| **Google Cloud Run** | Scale-to-zero, pay-per-use | 2M req/mois gratuit |
| **Oracle Cloud Free** | 2 VMs ARM toujours gratuites | Config plus complexe |

### Variables d'environnement en production

Ne jamais mettre les clés dans le code ou dans un fichier commité.  
Sur chaque plateforme, utiliser l'interface de gestion des secrets :

```
GROQ_API_KEY        → depuis console.groq.com/keys
MISTRAL_API_KEY     → depuis console.mistral.ai (si provider=mistral)
DEBUG_LOCAL         → false (impératif en prod)
ORDER_COMPLEXITY_THRESHOLD → 6
```

---

## Monitoring (optionnel)

L'application expose `/health` et `/api/status`. Pour aller plus loin :

### Grafana Cloud (gratuit)

1. Compte gratuit sur https://grafana.com (10 000 métriques, 50 GB logs, 14 jours)
2. Activer le plugin *Prometheus remote write* ou *Loki* pour les logs structurés
3. L'endpoint `/health` peut être sondé via **Grafana Synthetic Monitoring**

### Ajouter des métriques Prometheus à FastAPI

```bash
pip install prometheus-fastapi-instrumentator
```

```python
# Dans src/app.py, après la création de app :
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

Cela expose `/metrics` au format Prometheus (requêtes/s, latence p95, erreurs).

### Dashboard suggéré

| Métrique | Source | Alerte recommandée |
|----------|--------|-------------------|
| Latence p95 réponse LLM | `/metrics` | > 5 s |
| Taux d'erreur 5xx | `/metrics` | > 1 % |
| Commandes créées / heure | logs structurés | — |
| Santé TTS | `/api/status` | service down |

---

## Structure

```
src/
├── app.py              # FastAPI, endpoints, machine à états commande
├── factory.py          # Instanciation des providers selon .env
├── basket.py           # Logique panier (fonctions pures)
├── excel_export.py     # Export commandes Excel
├── logging_config.py   # Logging structuré RGPD
├── orders_store.py     # Stockage JSON des commandes
├── providers/          # Implémentations STT et LLM
├── prompts/            # Prompts versionnés (YAML)
└── menu/               # Menu et catalogue prix (YAML)
docs/
├── AIPD.md             # Analyse d'Impact relative à la Protection des Données
├── ARCHITECTURE.md     # Schéma des composants
└── DECISIONS.md        # Choix architecturaux (ADR-style)
tests/
├── test_basket.py      # 20 tests fonctions pures
├── test_excel.py       # 6 tests export Excel
├── test_factory.py     # 9 tests instanciation providers
├── test_logging_filter.py  # 8 tests filtre RGPD
├── promptfoo.yaml      # 20 cas golden set (seuil ≥ 90 %)
└── conversations/      # Scénarios complets avec assertions Excel
```

---

## Conformité RGPD / AI Act

- **AI Act art. 50** : l'agent annonce qu'il est une IA à chaque ouverture de session.
- **Logs** : aucune donnée personnelle loggée (filtre regex dans `logging_config.py`).
- **Mode 100 % local** : `STT_PROVIDER=local_ollama + LLM_PROVIDER=local_ollama` → aucune donnée ne quitte la machine.
- Voir `docs/AIPD.md` pour l'analyse complète.
