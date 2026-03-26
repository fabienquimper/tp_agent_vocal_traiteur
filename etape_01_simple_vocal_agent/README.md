# Étape 01 – Agent Vocal Traiteur (base)

Agent conversationnel vocal pour un traiteur français, basé sur LangGraph + modèles IA 100 % locaux dans Docker.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Navigateur (UI – port 3000)                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Texte ou Audio → nginx proxy → /api/*           │   │
│  └──────────────────────┬──────────────────────────┘   │
└─────────────────────────┼───────────────────────────────┘
                          │
        ┌─────────────────▼──────────────────┐
        │  Agent FastAPI (port 8000)          │
        │  ┌────────────────────────────────┐ │
        │  │  Graphe LangGraph              │ │
        │  │                                │ │
        │  │  transcribe → classify → route │ │
        │  │       ↓            ↓           │ │
        │  │  search_rag  process_order     │ │
        │  │       ↓            ↓           │ │
        │  │     generate_response          │ │
        │  │           ↓                    │ │
        │  │      synthesize                │ │
        │  └────────────────────────────────┘ │
        └──────┬────────────┬────────────┬────┘
               │            │            │
    ┌──────────▼──┐  ┌──────▼──┐  ┌─────▼──────┐
    │ STT :8001   │  │ TTS:8002│  │ Ollama:11434│
    │ Whisper     │  │  piper  │  │  Mistral    │
    │ (base)      │  │  (siwis)│  │             │
    └─────────────┘  └─────────┘  └─────────────┘
```

### Services Docker

| Service  | Port  | Rôle                                         | Modèle                          |
|----------|-------|----------------------------------------------|---------------------------------|
| `ollama` | 11434 | LLM local                                    | Mistral 7B                      |
| `stt`    | 8001  | Speech-to-Text                               | Whisper base (~145 MB)          |
| `tts`    | 8002  | Text-to-Speech (voix FR)                     | piper siwis-medium (~60 MB)     |
| `agent`  | 8000  | Orchestrateur LangGraph + RAG + Excel        | sentence-transformers (~90 MB)  |
| `ui`     | 3000  | Interface web (nginx)                        | –                               |

### Flux du graphe LangGraph

```
START
  └─→ [transcribe]      Si audio : appel STT → texte
  └─→ [classify]        LLM : intent + extraction articles
  └─→ route conditionnelle
        ├── "info"           → [search_rag] → [generate_response]
        ├── "commande_*"     → [process_order] → [generate_response]
        └── "autre"          → [generate_response]
  └─→ [synthesize]      Appel TTS → audio WAV
END
```

### Logique commandes

- **Commande simple** (≤ 6 unités) → `orders/commandes_simples.xlsx`
- **Commande complexe** (> 6 unités) → `orders/commandes_complexes.xlsx`

Le seuil est configurable via `ORDER_COMPLEXITY_THRESHOLD` dans `.env`.

---

## Démarrage rapide

### Prérequis

- Docker Desktop ≥ 24 avec Docker Compose
- 8 Go de RAM minimum recommandés (Mistral 7B ~4 Go)

### 1. Cloner / se positionner

```bash
cd etape_01_simple_vocal_agent
cp .env.example .env
```

### 2. Build + démarrage (première fois)

```bash
make init-all
```

Cette commande :
1. Construit les 4 images Docker (télécharge Whisper, piper, sentence-transformers)
2. Démarre tous les services
3. Télécharge le modèle Mistral dans Ollama (~4 Go, une seule fois)

### 3. Utilisation

Ouvrir **http://localhost:3000**

- **Texte** : saisir un message et appuyer sur Entrée ou ►
- **Voix** : maintenir le bouton 🎤, parler, relâcher

### Commandes utiles

```bash
make up           # Démarrer les services
make down         # Arrêter
make logs         # Logs en temps réel
make test         # Smoke tests curl
make test-health  # Santé de chaque service
make reload-docs  # Re-indexer data/ dans ChromaDB
make clean        # Tout supprimer (volumes inclus)
```

---

## Données de l'entreprise

Ajouter ou modifier les fichiers `.txt` dans `data/` :

```
data/
├── menus.txt      ← Produits, prix, formules
├── horaires.txt   ← Heures d'ouverture, contact
└── conges.txt     ← Congés, jours fériés
```

Après modification : `make reload-docs` pour re-indexer.

---

## API (exemples curl)

```bash
# Question texte (sans TTS)
curl -X POST http://localhost:8000/api/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Quels sont vos horaires le vendredi ?", "skip_tts": true}'

# Commande simple
curl -X POST http://localhost:8000/api/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Je voudrais 3 éclairs et 2 quiches lorraines", "skip_tts": true}'

# Commande complexe (>6 unités)
curl -X POST http://localhost:8000/api/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Je commande 4 poulets rôtis et 5 tartes aux pommes", "skip_tts": true}'

# Santé
curl http://localhost:8000/health
```

---

## Structure du projet

```
etape_01_simple_vocal_agent/
├── docker-compose.yml
├── Makefile
├── .env.example
├── data/                        ← Fichiers de l'entreprise (RAG)
│   ├── menus.txt
│   ├── horaires.txt
│   └── conges.txt
├── orders/                      ← Commandes Excel générées
├── scripts/
│   └── init_ollama.sh
├── services/
│   ├── stt/                     ← Service Speech-to-Text
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app.py
│   ├── tts/                     ← Service Text-to-Speech
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app.py
│   └── agent/                   ← Orchestrateur LangGraph
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── config.py        ← Variables d'environnement
│           ├── main.py          ← FastAPI endpoints
│           ├── graph/
│           │   ├── state.py     ← TypedDict état du graphe
│           │   ├── nodes.py     ← Fonctions de chaque nœud
│           │   └── workflow.py  ← Assemblage du graphe
│           ├── rag/
│           │   └── retriever.py ← Chargement docs + ChromaDB
│           └── orders/
│               └── writer.py   ← Écriture Excel
└── ui/                          ← Interface web (nginx)
    ├── Dockerfile
    ├── nginx.conf
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Prochaines étapes suggérées

- **Étape 02** : Ajout des tests (pytest, coverage ≥ 70 %, LLM mocké)
- **Étape 03** : Observabilité (Prometheus + Grafana)
- **Étape 04** : Sécurité (auth, rate limiting, détection prompt injection)
- **Étape 05** : CI/CD (GitHub Actions : lint → test → build → deploy)
- **Étape 06** : Déploiement Kubernetes + HPA
