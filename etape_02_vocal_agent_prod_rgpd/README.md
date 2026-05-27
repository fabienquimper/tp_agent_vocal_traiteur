# Étape 02 – Agent Vocal Traiteur (Production / RGPD)

Agent vocal pour la prise de commandes chez un traiteur.  
Architecture orientée **release applicative** : code + prompts + config modèles + menu versionnés.

---

## Prérequis

- Docker + Docker Compose
- Une clé API Groq gratuite → https://console.groq.com/keys  
  *(ou Mistral, ou Ollama en local — voir section Providers)*
- **Node.js 22** — requis pour `promptfoo` (golden set).  
  Si vous utilisez [nvm](https://github.com/nvm-sh/nvm) : `nvm use` suffit (`.nvmrc` inclus).

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

Aucune donnée ne quitte la machine. Un script de setup est fourni pour chaque plateforme :

| Plateforme | Script |
|------------|--------|
| Linux | `bash scripts/setup_ollama_local.sh` |
| WSL2 (Ollama sur Windows) | `bash scripts/setup_ollama_wsl.sh` |
| WSL2 (Ollama dans WSL) | `bash scripts/setup_ollama_wsl.sh --wsl` |
| Windows (PowerShell) | `.\scripts\setup_ollama_windows.ps1` |

Chaque script installe Ollama si nécessaire, télécharge le modèle et affiche la config `.env` à utiliser.

Puis dans `.env` :
```env
LLM_PROVIDER=local_ollama
LLM_MODEL=qwen2.5:7b
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

```bash
docker compose up
```

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

### Vue d'ensemble

| Suite | Commande | Réseau | Agent requis | Ce qu'elle vérifie |
|---|---|---|---|---|
| Unitaires | `pytest -m "not slow"` | ❌ | ❌ | Logique panier, export Excel, providers, filtre RGPD |
| Prompts (golden set) | `promptfoo eval` | ✅ | ✅ | Qualité des réponses LLM (≥ 90 % de cas passants) |
| Conversations | `pytest -m slow` | ✅ | ✅ | Scénarios complets multi-tours avec assertions |

### Prérequis : environnement virtuel Python

Les tests unitaires tournent directement sur votre machine, sans Docker.  
Il faut Python 3.11+ et un environnement virtuel pour isoler les dépendances.

**Créer et activer le venv — une seule fois :**

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Windows (CMD)
python -m venv .venv
.venv\Scripts\activate.bat

# Windows (Git Bash) · WSL · Mac · Linux
python3 -m venv .venv
source .venv/bin/activate
```

> Le prompt de votre terminal doit afficher `(.venv)` une fois activé.  
> Pour désactiver : `deactivate`

**Installer les dépendances :**

```bash
python -m pip install -r requirements.txt
```

> `python -m pip` garantit d'utiliser le pip du venv actif, même si bash a mis en cache un pip système.  
> À refaire uniquement si `requirements.txt` change.

### Tests unitaires — lancement rapide

Pas besoin de Docker ni de clé API. Venv activé et dépendances installées :

```bash
pytest -m "not slow"          # 51 tests, < 3 s
pytest -m "not slow" -v       # verbose (détail de chaque test)
pytest tests/test_basket.py   # une suite uniquement
```

Les 4 suites couvertes :
- `test_basket.py` — calcul du panier, correspondance produits, total
- `test_excel.py` — création fichier, colonnes, ajout multiple
- `test_factory.py` — clé manquante → EnvironmentError, provider inconnu → ValueError
- `test_logging_filter.py` — CB, téléphone, e-mail scrubés ; référence commande préservée

### Tests de prompts (golden set)

Vérifient que le LLM répond correctement sur 25 cas représentatifs.  
Nécessitent l'agent démarré (`docker compose up`) et promptfoo installé :

```bash
nvm use                          # sélectionne Node 22 via .nvmrc (si nvm installé)
npm install -g promptfoo         # une fois
docker compose up -d             # agent en arrière-plan
promptfoo eval --config tests/promptfoo.yaml
```

Catégories couvertes : commandes nominales, questions menu, ingrédients, allergènes,
délais, livraison, jailbreak, transparence IA (AI Act art. 50), questions de suivi.

**Ajouter un cas :** éditer `tests/promptfoo.yaml`, ajouter un bloc dans la liste `tests:` :

```yaml
- description: "Mon nouveau cas"
  vars:
    message: "Votre question ici"
  assert:
    - type: llm-rubric
      value: "Ce que la réponse doit contenir ou faire"
    - type: contains          # optionnel : vérification exacte
      value: "mot clé"
```

### Tests de conversation complets

Simulent des scénarios end-to-end : commande → collecte client → paiement → Excel.  
Nécessitent l'agent démarré avec un LLM réel :

```bash
docker compose up -d
pytest -m slow -v
```

Scénarios disponibles dans `tests/conversations/` :
- `conv_01_anniv_50pers.json` — commande anniversaire 50 personnes (complexe)
- `conv_02_repas_pro.json` — repas professionnel multi-plats
- `conv_03_jailbreak.json` — tentative de détournement → refus attendu
- `conv_04_pronoun_reference.json` — résolution pronominale ("j'en veux 4" après info sur un plat)
- `conv_05_remove_item.json` — suppression d'un article du panier en cours
- `conv_06_view_basket.json` — consultation du panier sans modifier la commande
- `conv_07_modify_quantity.json` — modification de quantité ("gardes-en que 3")
- `conv_09_changement_avis.json` — remplacement de panier ("à la place") — ⚠️ régression connue, marqué `xfail`

Chaque scénario inclut des assertions sur le panier et/ou le fichier Excel généré.
(colonnes, montant, type de commande).

**Lancer un seul scénario :**
```bash
pytest tests/test_conversations.py::test_conv_09_changement_avis -v -m slow --timeout=120
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

## Dépannage

### Port 8000 déjà utilisé au démarrage

```
failed to bind host port 0.0.0.0:8000/tcp: address already in use
```

Les services ont `restart: unless-stopped` : Docker les relance automatiquement au démarrage
de la machine, même sans `docker compose up` explicite. Si un conteneur d'une session
précédente n'a pas été supprimé proprement, il reprend le port au boot.

**Bonne pratique :** toujours terminer avec `docker compose down` plutôt que `Ctrl+C`.
Le `Ctrl+C` arrête les conteneurs mais les laisse enregistrés avec la politique de restart.

```bash
# Stopper et supprimer les conteneurs proprement
docker compose down

# Si le port reste bloqué (proxy Docker fantôme), identifier le processus :
ss -tlnp sport = :8000
# Puis tuer le docker-proxy correspondant :
sudo kill <PID>
```

### Ollama inaccessible depuis Docker (`All connection attempts failed`)

Ollama écoute par défaut sur `127.0.0.1` — invisible depuis les conteneurs Docker.
Le script `setup_ollama_local.sh` corrige ça automatiquement. Si le problème persiste :

```bash
# Ollama installé en snap (Ubuntu)
sudo snap set ollama host=0.0.0.0
sudo snap restart ollama

# Ollama installé classiquement
export OLLAMA_HOST=0.0.0.0   # ajouter dans ~/.bashrc pour le rendre permanent
pkill -f "ollama serve" && OLLAMA_HOST=0.0.0.0 ollama serve &
```

**Alternative — IP locale directe** (utile si `host.docker.internal` ne fonctionne pas) :

```bash
# Trouver l'IP de la machine sur le réseau local
ip route get 1 | awk '{print $7; exit}'   # ex : 192.168.1.42
```

Dans `.env` :
```env
OLLAMA_BASE_URL=http://192.168.1.42:11434   # remplacer par votre IP
```

Cette approche évite `host.docker.internal` et fonctionne sur toutes les configurations Docker.

---

## Conformité RGPD / AI Act

- **AI Act art. 50** : l'agent annonce qu'il est une IA à chaque ouverture de session.
- **Logs** : aucune donnée personnelle loggée (filtre regex dans `logging_config.py`).
- **Mode 100 % local** : `STT_PROVIDER=local_ollama + LLM_PROVIDER=local_ollama` → aucune donnée ne quitte la machine.
- Voir `docs/AIPD.md` pour l'analyse complète.
