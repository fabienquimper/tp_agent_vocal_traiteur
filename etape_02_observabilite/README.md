# Étape 02 – Observabilité : Prometheus + Grafana

> **Prérequis :** avoir complété l'étape 01 et compris l'architecture de base.
>
> **Concept clé :** *"On ne peut pas optimiser ce qu'on ne mesure pas."*
> Avant de changer de modèle Whisper (étape 03), il faut savoir où passe le temps.

---

## Ce qu'on ajoute dans cette étape

| Étape 01 | Étape 02 (nouveau) |
|---|---|
| Agent vocal fonctionnel | + Prometheus scrape `/metrics` toutes les 15s |
| LangGraph + RAG + TTS | + Grafana avec dashboard auto-provisionné |
| Docker multi-services | + 2 nouveaux services : `prometheus` + `grafana` |
| Logs dans la console | + **Métriques structurées** par composant du pipeline |

### Nouveaux fichiers

```
etape_02_observabilite/
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml              ← config scrape (cible: agent:8000/metrics)
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── datasources.yml     ← datasource Prometheus (uid fixe!)
│           └── dashboards/
│               ├── dashboards.yml      ← provider: cherche les JSON dans ce dossier
│               └── vocal_agent.json    ← dashboard "Agent Vocal Traiteur — Pipeline IA"
└── services/agent/app/
    └── metrics.py                      ← toutes les métriques Prometheus
```

### Fichiers modifiés vs étape 01

| Fichier | Modification |
|---|---|
| `docker-compose.yml` | + services `prometheus` et `grafana` + volumes |
| `services/agent/requirements.txt` | + `prometheus_client==0.21.1` |
| `services/agent/app/main.py` | + endpoint `GET /metrics` + instrumentation sessions/paiements |
| `services/agent/app/graph/nodes.py` | + timers `time.perf_counter()` sur chaque nœud |

---

## Architecture de monitoring

```
┌─────────────────────────────────────────────────────────────────┐
│                     PIPELINE VOCAL                              │
│                                                                 │
│  Audio → [STT/Whisper] → texte → [LLM classify] → intent      │
│                                      ↓                         │
│                               [RAG/ChromaDB]                   │
│                                      ↓                         │
│                            [LLM generate] → texte              │
│                                      ↓                         │
│                            [TTS/Piper] → audio                 │
│                                                                 │
│  Chaque étape expose ses métriques via /metrics                 │
└──────────────────┬──────────────────────────────────────────────┘
                   │ GET /metrics (toutes les 15s)
                   ▼
         ┌─────────────────┐
         │   Prometheus    │  port 9090
         │   (TSDB)        │  stockage 7 jours
         └────────┬────────┘
                  │ PromQL queries
                  ▼
         ┌─────────────────┐
         │    Grafana      │  port 3001
         │   (Dashboard)   │  auto-provisionné
         └─────────────────┘
```

---

## Démarrage

```bash
# Première fois
make init-all

# Démarrages suivants
make up
make init-ollama   # si modèle Mistral pas encore téléchargé
```

**Services accessibles :**

| Service | URL | Description |
|---|---|---|
| Interface | http://localhost:3000 | Agent vocal (inchangé) |
| Agent API | http://localhost:8000 | + `/metrics` disponible |
| Prometheus | http://localhost:9090 | Explorateur de métriques |
| **Grafana** | **http://localhost:3001** | **Dashboard auto-provisionné** |

---

## Explorer les métriques

### 1. Via curl (métriques brutes)

```bash
# Voir les métriques instrumentées
make metrics

# Exemple de sortie après quelques requêtes :
# stt_latency_seconds_count 3.0
# stt_latency_seconds_sum 4.231
# llm_classify_requests_total{intent="info"} 2.0
# llm_classify_requests_total{intent="commande_simple"} 1.0
# rag_requests_total{result="hit"} 2.0
# conversation_duration_seconds_count 3.0
```

### 2. Via Prometheus (http://localhost:9090)

Taper dans la barre de recherche :

```promql
# Latence P95 du pipeline complet (secondes)
histogram_quantile(0.95, rate(conversation_duration_seconds_bucket[5m]))

# Latence P95 du STT uniquement
histogram_quantile(0.95, rate(stt_latency_seconds_bucket[5m]))

# Taux de requêtes par minute (toutes intents)
rate(llm_classify_requests_total[5m]) * 60

# Hit rate RAG (proportion de requêtes qui trouvent des documents)
rate(rag_requests_total{result="hit"}[5m]) /
rate(rag_requests_total[5m])

# Sessions actives en ce moment
sessions_active
```

### 3. Via Grafana (http://localhost:3001)

Le dashboard **"Agent Vocal Traiteur — Pipeline IA"** est automatiquement disponible
dans le dossier **Traiteur Dupont**.

Il contient :
- **Vue d'ensemble** : conversations/24h, sessions actives, commandes, taux d'erreur, hit rate RAG
- **Latence bout-en-bout** : P50 / P95 / P99 de la durée totale (SLA cible : P95 < 10s)
- **STT** : latence Whisper P50/P95, compteur d'erreurs
- **LLM** : latence classification P50/P95, latence génération P50/P95, distribution des intents
- **RAG** : latence ChromaDB, chunks récupérés en moyenne
- **TTS** : latence Piper P50/P95
- **Business** : commandes simple/complexe, paiements CB/liquide/sur place

### 4. Générer du trafic pour voir les graphes

```bash
# Envoie 10 requêtes pour alimenter les métriques
make traffic

# Puis rechargez Grafana (ou attendez 30s — refresh automatique)
```

---

## Concepts clés

### Les 3 types de métriques Prometheus

```python
# Counter : valeur qui ne fait qu'augmenter
# → Nombre de requêtes, nombre d'erreurs
# → PromQL : rate(metric[5m]) pour avoir un taux par seconde
conversations_total = Counter("conversations_total", "...")

# Histogram : distribution statistique
# → Latences, tailles de fichiers
# → PromQL : histogram_quantile(0.95, rate(metric_bucket[5m])) pour P95
stt_latency_seconds = Histogram("stt_latency_seconds", "...",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0])

# Gauge : valeur qui monte et descend
# → Sessions actives, RAM utilisée, connexions ouvertes
# → PromQL : utiliser la valeur directement
sessions_active = Gauge("sessions_active", "...")
```

### Modèle Pull de Prometheus

```
┌─────────┐   GET /metrics   ┌────────────┐
│ Agent   │ ◄──────────────── │ Prometheus │
│ :8000   │                   │ :9090      │
└─────────┘   toutes les 15s  └────────────┘
```

**Avantages du pull :**
- Prometheus sait immédiatement si un service est KO (scrape timeout)
- Pas de couplage entre le service et le système de monitoring
- La fréquence est contrôlée centralement (dans prometheus.yml)

**Alternative push (StatsD, InfluxDB Line Protocol) :**
- Le service envoie les métriques lui-même
- Avantage : fonctionne derrière des firewalls très restrictifs
- Inconvénient : si le service crashe, les métriques s'arrêtent silencieusement

### UID de datasource fixe dans Grafana

```yaml
# datasources.yml
datasources:
  - uid: prometheus   # ← FIXE, jamais aléatoire
```

Sans UID fixe, Grafana génère un identifiant aléatoire à chaque redémarrage.
Tous les panels du dashboard perdent leur source et affichent "No data".

---

## Décomposition du temps de réponse

Après quelques conversations, vous pouvez voir dans Grafana **où passe le temps** :

| Composant | Temps typique (modèle `base` / CPU) |
|---|---|
| STT (Whisper base) | 0.5 – 2.5s |
| LLM classify (Mistral 7B) | 2 – 8s |
| RAG (ChromaDB) | 0.05 – 0.3s |
| LLM generate (Mistral 7B) | 3 – 12s |
| TTS (Piper) | 0.3 – 1.5s |
| **Total P95** | **~8 – 25s** |

**Question pédagogique :** Quel composant est le goulot d'étranglement ?

> Réponse : Le LLM (Mistral 7B sur CPU) est appelé **deux fois** (classify + generate).
> L'étape 03 exploitera ces mesures pour comparer Whisper `base` vs `small` vs `medium` :
> est-ce que passer à un meilleur modèle de transcription améliore la qualité
> sans détériorer la latence totale de manière inacceptable ?

---

## Commandes utiles

```bash
make up            # Démarre tous les services (dont Prometheus + Grafana)
make test-health   # Vérifie que tous les services répondent
make metrics       # Affiche les métriques brutes de l'agent
make traffic       # Génère du trafic pour alimenter Grafana
make grafana       # Ouvre Grafana dans le navigateur
make prometheus    # Ouvre Prometheus dans le navigateur
make reload-docs   # Re-indexe les fichiers RAG
make logs          # Logs en temps réel
make down          # Arrête tout
make clean         # Arrête + supprime les volumes (ChromaDB + Prometheus + Grafana)
```

---

## Ce que prépare cette étape

L'observabilité est la fondation de toutes les décisions d'optimisation.

```
Étape 02 → on mesure → on a une baseline
Étape 03 → on compare Whisper base vs small vs medium
           avec les MÊMES métriques → décision data-driven

Questions que l'étape 03 va pouvoir répondre objectivement :
  - Le modèle "small" améliore-t-il la précision de transcription ?
  - De combien augmente la latence STT P95 ?
  - Le gain de qualité vaut-il le surcoût de latence ?
  - Comment déployer le nouveau modèle sans interrompre le service ?
    (→ concept de Blue/Green deployment + hot reload)
```
