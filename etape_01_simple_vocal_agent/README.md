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

- Docker Engine ≥ 24 avec Docker Compose
- 8 Go de RAM minimum recommandés (Mistral 7B ~4 Go)

### Résolution des problèmes connus (Ubuntu 24.04 Noble + Docker 28.x)

#### R��seau inter-containers bloqué avec `runtime: nvidia` (Ubuntu + UFW)

**Symptôme** : nginx (UI) et l'agent ne peuvent pas joindre les autres services via le nom Docker (`ollama:11434`, `agent:8000`). Erreur `[Errno 110] Connection timed out` dans les logs.

**Cause** : `runtime: nvidia` sur le container Ollama, combiné à UFW actif sur Ubuntu, bloque le forwarding iptables entre containers sur le même bridge Docker.

**Fixes appliqués dans ce projet** :
1. Autoriser le sous-réseau Docker dans UFW :
   ```bash
   sudo ufw allow from 172.20.0.0/16
   sudo ufw allow to 172.20.0.0/16
   ```
2. Utiliser `host.docker.internal` au lieu des noms de service Docker dans les configs proxy, avec `extra_hosts: ["host.docker.internal:host-gateway"]` dans `docker-compose.yml` pour les services `agent` et `ui`.

---

#### HuggingFace Hub bloque le démarrage (réseau hors-ligne ou lent)

**Symptôme** : les containers `stt` et `agent` restent en `health: starting` pendant 5+ minutes. Logs : `Max retries exceeded... Failed to establish a new connection`.

**Cause** : `huggingface_hub` tente de contacter `huggingface.co` au démarrage pour vérifier si une nouvelle version du modèle est disponible, même si le modèle est déjà en cache local.

**Fix** : `HF_HUB_OFFLINE=1` dans l'environnement des services `stt` et `agent` (déjà présent dans ce `docker-compose.yml`).

---

#### STT charge le mauvais device (`cuda` sur image sans CUDA)

**Symptôme** : `docker logs traiteur_stt` affiche `Chargement du modèle Whisper 'xxx' sur cuda...` puis le container reste bloqué.

**Cause** : `.env` contenait `WHISPER_DEVICE=cuda` mais l'image `python:3.11-slim` n'a pas les libs CUDA.

**Fix** : `.env` → `WHISPER_DEVICE=cpu`. Le service STT reste en CPU dans ce TP.

---

#### Bug iptables : `Chain 'DOCKER-ISOLATION-STAGE-2' does not exist`

Docker 28.x sur Ubuntu 24.04 avec kernel 6.x utilise `iptables-nft` en interne et oublie de créer la chaîne `DOCKER-ISOLATION-STAGE-2` au démarrage. Symptôme :

```
failed to create network: iptables v1.8.10 (nf_tables): Chain 'DOCKER-ISOLATION-STAGE-2' does not exist
```

**Fix immédiat** (à relancer après chaque redémarrage de Docker si le service ci-dessous n'est pas installé) :

```bash
sudo iptables-nft -t filter -N DOCKER-ISOLATION-STAGE-1 2>/dev/null || true
sudo iptables-nft -t filter -N DOCKER-ISOLATION-STAGE-2 2>/dev/null || true
```

**Fix persistant** (crée un service systemd qui tourne avant Docker) :

```bash
sudo tee /etc/systemd/system/docker-iptables-fix.service << 'EOF'
[Unit]
Description=Cree les chaines iptables manquantes pour Docker 28.x
After=network.target
Before=docker.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/iptables-nft -t filter -N DOCKER-ISOLATION-STAGE-1
ExecStart=/usr/sbin/iptables-nft -t filter -N DOCKER-ISOLATION-STAGE-2
IgnoreExitCode=yes
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now docker-iptables-fix
```

#### GPU NVIDIA (optionnel) — RTX 4070 / RTX 3xxx etc.

Ollama utilise automatiquement le GPU si `nvidia-container-toolkit` est installé.

```bash
# 1. Clé GPG
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg --yes

# 2. Dépôt (une seule ligne)
echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/amd64 /" | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# 3. Installer
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# 4. Configurer Docker
sudo nvidia-ctk runtime configure --runtime=docker

# 5. Générer le spec CDI (décrit les devices GPU pour Docker)
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# 6. Ajouter libnvidia-ml au cache ldconfig
#    (la lib n'a pas de SONAME donc ldconfig ne la trouve pas automatiquement)
echo "/usr/lib/x86_64-linux-gnu" | sudo tee /etc/ld.so.conf.d/nvidia-ml.conf
sudo ldconfig

# 7. Forcer le mode CDI dans le runtime nvidia
sudo sed -i 's/^mode = "auto"/mode = "cdi"/' /etc/nvidia-container-runtime/config.toml
sudo sed -i 's/skip-mode-detection = false/skip-mode-detection = true/' /etc/nvidia-container-runtime/config.toml

# 8. Redémarrer Docker + recréer les chaînes iptables (bug Docker 28.x)
sudo systemctl restart docker
sudo iptables-nft -t filter -N DOCKER-ISOLATION-STAGE-1 2>/dev/null || true
sudo iptables-nft -t filter -N DOCKER-ISOLATION-STAGE-2 2>/dev/null || true

# 9. Vérifier (doit afficher le modèle GPU)
nvidia-container-cli info
```

> **Architecture GPU dans ce projet** : seul Ollama (LLM) utilise le GPU via
> `runtime: nvidia` + `NVIDIA_VISIBLE_DEVICES=all`. Le service STT (faster-whisper)
> reste en CPU car son image `python:3.11-slim` ne contient pas CUDA.
>
> **Pourquoi `runtime: nvidia` plutôt que `deploy.resources` ?** L'approche
> `deploy.resources.reservations.devices` fait injecter le hook par Docker lui-même,
> qui ignore `config.toml`. Avec `runtime: nvidia`, c'est `nvidia-container-runtime`
> qui gère l'injection et lit correctement la configuration CDI.

Le Makefile détecte automatiquement le GPU (`nvidia-container-cli info`) et charge `docker-compose.gpu.yml` si disponible.

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

## Mode HuggingFace (APIs distantes)

Si les traitements IA sont trop lents sur votre machine (pas de GPU, CPU modeste), vous pouvez remplacer les trois modèles locaux par des appels à l'**API HuggingFace Inference** — gratuite pour un usage modéré.

| Service     | Modèle local              | Modèle HuggingFace (défaut)                  |
|-------------|--------------------------|----------------------------------------------|
| STT (voix)  | Whisper base (~145 MB)   | `openai/whisper-large-v3` (plus précis)      |
| TTS (parole)| piper siwis-medium       | `hexgrad/Kokoro-82M`                         |
| LLM (agent) | Mistral 7B via Ollama    | `Qwen/Qwen2.5-7B-Instruct` (multilingue)    |

### 1. Obtenir un token HuggingFace (gratuit)

1. Créer un compte sur [huggingface.co](https://huggingface.co)
2. Aller dans **Settings → Access Tokens**
3. Créer un token avec le rôle **Read** (ou *Inference*)
4. Copier le token (`hf_xxxxxxxxxxxx`)

### 2. Démarrer en mode HuggingFace

```bash
# Option A – via Makefile (recommandé)
make up-hf HF_API_TOKEN=hf_xxxxxxxxxxxx

# Option B – via docker compose directement
HF_API_TOKEN=hf_xxxxxxxxxxxx \
  docker compose -f docker-compose.yml -f docker-compose.hf.yml \
  up -d stt tts agent ui
```

> **Remarque** : Ollama n'est pas démarré — inutile en mode HF.
> Le premier appel peut prendre ~20–30 s le temps que HuggingFace charge le modèle en mémoire.

### 3. Changer de modèle (optionnel)

Les modèles HF sont configurables via variables d'environnement :

```bash
HF_API_TOKEN=hf_xxx \
HF_LLM_MODEL=mistralai/Mixtral-8x7B-Instruct-v0.1 \
HF_STT_MODEL=openai/whisper-large-v3 \
HF_TTS_MODEL=facebook/mms-tts-fra \
  make up-hf
```

Ou dans votre `.env` :
```
HF_API_TOKEN=hf_xxxxxxxxxxxx
HF_LLM_MODEL=mistralai/Mistral-7B-Instruct-v0.3
HF_STT_MODEL=openai/whisper-large-v3
HF_TTS_MODEL=facebook/mms-tts-fra
```

### 4. Revenir en mode local

```bash
make down
make up   # redémarre avec Ollama local
```

### Comparaison des modes

| Critère               | Mode local                  | Mode HuggingFace            |
|-----------------------|-----------------------------|-----------------------------|
| Confidentialité       | 100 % (aucune donnée sortante) | Audio/texte envoyés à HF  |
| Vitesse (sans GPU)    | Lent (30–120 s/requête LLM) | Rapide (~2–5 s)             |
| Coût                  | Gratuit                     | Gratuit (quota API HF)      |
| Disponibilité         | Toujours (hors-ligne OK)    | Nécessite Internet          |
| Qualité STT           | Whisper base (correct)      | Whisper large-v3 (excellent)|

---

## Prochaines étapes suggérées

- **Étape 02** : Ajout des tests (pytest, coverage ≥ 70 %, LLM mocké)
- **Étape 03** : Observabilité (Prometheus + Grafana)
- **Étape 04** : Sécurité (auth, rate limiting, détection prompt injection)
- **Étape 05** : CI/CD (GitHub Actions : lint → test → build → deploy)
- **Étape 06** : Déploiement Kubernetes + HPA

# Interface

Voici un exemple d'interface d'échange (avec transcription audio)

![alt text](image.png)