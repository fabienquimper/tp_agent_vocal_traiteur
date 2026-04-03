# Parcours complet — Traiteur Dupont : Agent Vocal IA

> **17 étapes** pour construire, déployer et opérer un agent vocal IA en production.
> Du prototype local jusqu'au cluster Kubernetes avec observabilité complète et déploiements progressifs automatisés.

---

## La problématique centrale

**Traiteur Dupont** veut remplacer sa ligne téléphonique par un agent vocal IA capable de :
- Prendre des commandes par la voix
- Répondre aux questions sur le menu (RAG)
- Calculer les prix et confirmer les commandes
- Fonctionner 24h/24 sans opérateur humain

Ce projet n'est pas trivial : il mêle LLM local, speech-to-text, text-to-speech, base vectorielle, et doit être robuste en production. Chaque étape résout un problème réel qui apparaît naturellement dans le cycle de vie d'une application IA.

---

## Carte du parcours

```
Phase 1 — Conception & Prototype
  00a UX/UI ──────── Maquetter avant de coder
  01  Agent base ─── LangGraph + Ollama + ChromaDB + Whisper + Piper

Phase 2 — Qualité & Mesure
  02  Observabilité ─ Prometheus + Grafana : mesurer pour optimiser
  03  Benchmark ───── Blue/Green Whisper : comparer base vs small
  04  Hot RAG ──────── Shadow indexing + atomic pointer swap
  05  Quality Gates ── Tests RAG avant mise en production

Phase 3 — Environnements
  06  Staging/Prod ─── Deux environnements Docker Compose isolés
  07  Kubernetes ────── Replicas + HPA + Rolling Update
  08  CI/CD ──────────── GitHub Actions : tests + build + déploiement

Phase 4 — GitOps & Observabilité avancée
  09  GitOps ──────── ArgoCD : Git comme source de vérité
  10  OpenTelemetry ── Traces distribuées + Jaeger

Phase 5 — Production avancée
  11  Canary ──────── Traffic splitting NGINX Ingress
  12  Security ────── Network Policies + RBAC (Zero Trust)
  13  Helm ────────── Chart packaging + values overrides

Phase 6 — Fiabilité & Observabilité complète
  14  SLOs & Alerting ─ Error budgets + AlertManager
  15  Argo Rollouts ─── Progressive delivery automatisé
  16  Loki ────────────── Les 3 piliers : Métriques + Traces + Logs
```

---

## Les étapes en détail

### Phase 1 — Conception & Prototype

#### `etape_00a_ux_ui/` — UX/UI : Concevoir avant de coder
**Problème :** Les développeurs ont tendance à coder d'abord et à réfléchir à l'UX ensuite. Résultat : des interfaces qui ne correspondent pas aux besoins réels.

**Ce qu'on fait :** Maquetter l'interface vocale dans Penpot (gratuit, open-source) avant d'écrire une ligne de code.

**Concept clé :** Le design system. Une palette de couleurs + une typographie + des composants réutilisables = une interface cohérente sans effort.

**Ce qui change :** On arrive à l'étape 01 avec une vision claire de ce qu'on construit.

---

#### `etape_01_simple_vocal_agent/` — Agent vocal de base
**Problème :** Comment construire un agent conversationnel vocal avec des LLMs 100% locaux ?

**Ce qu'on fait :**
- **LangGraph** : orchestre le flux de conversation (états, transitions, outils)
- **Ollama + Mistral 7B** : LLM local (aucune donnée envoyée vers le cloud)
- **ChromaDB** : base vectorielle pour le RAG (Retrieval-Augmented Generation) sur le menu
- **Whisper** : speech-to-text (transcription de la voix)
- **Piper** : text-to-speech (synthèse vocale en français)
- **FastAPI** : API REST + WebSocket pour l'interface web

**Architecture :**
```
Voix → Whisper → LangGraph → Ollama/Mistral
                    ↑              ↓
                 ChromaDB      Piper → Audio
```

**Ce qui change :** On a un agent qui fonctionne. Il est lent et fragile. Les étapes suivantes corrigent ça.

---

### Phase 2 — Qualité & Mesure

#### `etape_02_observabilite/` — Prometheus + Grafana
**Problème :** L'agent est lent parfois. Mais où ? Whisper ? Le LLM ? Le RAG ? Sans mesures, on optimise à l'aveugle.

**Ce qu'on fait :**
- Instrumenter FastAPI avec `prometheus_fastapi_instrumentator`
- Ajouter des métriques custom : `conversations_total`, `rag_quality_score`, `llm_duration_seconds`
- Visualiser dans Grafana (panels, time range, alerting)

**Concept clé :** *"On ne peut pas optimiser ce qu'on ne mesure pas."* — Cette étape est le fondement de toutes les décisions qui suivent.

**Ce qui change :** On voit que 70% du temps est dans Whisper. L'étape suivante en tire parti.

---

#### `etape_03_benchmark_whisper/` — Blue/Green Whisper
**Problème :** Whisper `base` est rapide mais imprécis, `small` est précis mais lent. Comment choisir ? Comment tester en production sans risque ?

**Ce qu'on fait :**
- **Blue/Green deployment** : deux versions en parallèle (`stt-blue` et `stt-green`)
- **stt-router** : un Service K8s qui redirige vers la couleur active
- **Benchmarks automatisés** avec les métriques Prometheus de l'étape 02

**Concept clé :** Le Blue/Green permet de basculer instantanément entre versions et de revenir en arrière si quelque chose cloche.

```
stt-router Service
    ├── stt-blue (Whisper base)   ← actif par défaut
    └── stt-green (Whisper small) ← en attente
```

**Ce qui change :** On peut comparer deux modèles en production réelle sans downtime.

---

#### `etape_04_hot_rag_reload/` — Shadow Indexing + Atomic Swap
**Problème :** Le menu du traiteur change. Mettre à jour le RAG nécessite de reconstruire ChromaDB (~30 secondes de downtime). Inacceptable.

**Ce qu'on fait :**
- **Shadow indexing** : reconstruire le nouvel index en parallèle, sans toucher à la production
- **Atomic pointer swap** : basculer en une ligne (`self._collection = new_collection`)
- Endpoint `/api/rag/reload` + monitoring du rebuild

**Concept clé :** En production, les mises à jour doivent être invisibles pour les utilisateurs. L'atomic swap est une technique universelle : elle s'applique aux bases de données, aux caches, aux configurations.

**Ce qui change :** Le menu peut être mis à jour à tout moment sans interrompre le service.

---

#### `etape_05_quality_gates/` — Tests avant l'Atomic Swap
**Problème :** Un rebuild sans erreur n'est pas forcément un bon rebuild. Si les nouvelles données RAG sont de mauvaise qualité, les réponses se dégradent silencieusement.

**Ce qu'on fait :**
- Tests automatiques après le rebuild : précision RAG sur un jeu de questions de référence
- **Quality Gate** : bloquer le swap si le score < seuil (ex: 0.8)
- Rollback automatique vers l'ancien index si le gate échoue

**Concept clé :** *Shift Left* — détecter les régressions avant que les utilisateurs les voient, pas après.

**Ce qui change :** Le RAG ne peut plus se dégrader silencieusement. Chaque mise à jour est validée avant d'atteindre la production.

---

### Phase 3 — Environnements

#### `etape_06_staging_production/` — Deux environnements isolés
**Problème :** On teste en production parce qu'on n'a pas d'environnement de staging. C'est risqué.

**Ce qu'on fait :**
- `docker-compose.staging.yml` + `docker-compose.prod.yml`
- Données de test isolées (menu factice en staging)
- **Promote workflow** : tester en staging → valider → promouvoir en production

**Concept clé :** Infrastructure as Code. Un fichier YAML décrit un environnement entier. Reproductible, versionnable, partageable.

**Ce qui change :** On peut casser les choses en staging sans impact sur la production.

---

#### `etape_07_kubernetes/` — Replicas, HPA, Rolling Update
**Problème :** Docker Compose orchestre 1 machine. En production, on veut de la haute disponibilité, du scaling automatique, des mises à jour sans downtime.

**Ce qu'on fait :**
- **Deployment** K8s : déclarer l'état désiré (N replicas)
- **HPA** (Horizontal Pod Autoscaler) : scaler automatiquement selon le CPU
- **Rolling Update** : remplacer les pods un à un (zero downtime)
- **kind** : cluster K8s local pour le développement

**Concept clé :** *"Docker Compose orchestre 1 machine. Kubernetes orchestre un cluster."*

**Ce qui change :** L'application peut maintenant survivre à la panne d'un pod, scaler sous charge, et se mettre à jour sans interruption.

---

#### `etape_08_cicd/` — GitHub Actions : CI/CD automatisé
**Problème :** Les tests sont exécutés manuellement, parfois oubliés. Les déploiements sont des procédures manuelles sujettes aux erreurs.

**Ce qu'on fait :**
- **CI** (`.github/workflows/ci.yml`) : tests unitaires + lint + build image à chaque push
- **CD** (`.github/workflows/cd.yml`) : déploiement automatique sur kind après validation CI
- **Mock Ollama** : remplace Ollama (4 GB) en CI pour économiser la RAM des runners

**Concept clé :** *"Le code non testé automatiquement est du code qui se casse en production."*

**Ce qui change :** Chaque commit est validé automatiquement. Le déploiement devient un acte banal, pas une cérémonie.

---

### Phase 4 — GitOps & Observabilité avancée

#### `etape_09_gitops/` — ArgoCD : Git comme source de vérité
**Problème :** Le CD de l'étape 08 *pousse* (`kubectl apply`). Si quelqu'un modifie le cluster manuellement, l'état réel diverge de ce qui est dans Git. Sans détection.

**Ce qu'on fait :**
- **ArgoCD** surveille le dépôt Git et *tire* (pull model) les changements
- Détection de dérive automatique (cluster ≠ Git → alerte)
- Sync automatique ou manuel
- Interface UI ArgoCD pour visualiser l'état de toutes les applications

**Concept clé :** *"Git est la seule source de vérité. Toute modification hors de Git est une dérive."*

```
Git (source de vérité)
    ↑ push
Développeur
    
ArgoCD ─── pull ──→ Git
    │
    └── apply ──→ Kubernetes (état réel)
```

**Ce qui change :** Le cluster est auto-réconcilié avec Git. Toute dérive est détectée et peut être corrigée automatiquement.

---

#### `etape_10_opentelemetry/` — Traces distribuées avec Jaeger
**Problème :** Prometheus dit "la requête a pris 8 secondes". Mais où ? Dans Whisper ? LangGraph ? Ollama ? ChromaDB ? On ne sait pas.

**Ce qu'on fait :**
- **OpenTelemetry SDK** : instrumenter FastAPI + LangGraph pour émettre des spans
- **Jaeger** : collecter et visualiser les traces
- Chaque requête vocale génère une trace avec des spans : `transcribe`, `rag.search`, `llm.invoke`, `tts.synthesize`

**Concept clé :** *"Les métriques disent QUOI, les traces disent POURQUOI."*

```
Requête vocale ──→ [span: transcribe 2s]
                   [span: rag.search 0.3s]
                   [span: llm.invoke 5.2s]  ← goulot d'étranglement
                   [span: tts.synthesize 0.5s]
```

**Ce qui change :** On peut identifier précisément quel composant est lent, sans hypothèse.

---

### Phase 5 — Production avancée

#### `etape_11_canary/` — Traffic splitting NGINX Ingress
**Problème :** Les Rolling Updates déploient pour 100% des utilisateurs d'un coup. Si la nouvelle version a un bug subtil, tout le monde est impacté.

**Ce qu'on fait :**
- **Canary Release** : déployer sur 10% du trafic d'abord
- **NGINX Ingress** : annotations `nginx.ingress.kubernetes.io/canary-weight: "10"`
- Observer les métriques Prometheus sur le subset canary
- Promotion progressive ou rollback selon les métriques

**Concept clé :** *"Deploy to 1% first, watch the metrics, then deploy to the world."*

**Ce qui change :** Un bug dans la nouvelle version n'impacte que 10% des utilisateurs. On a le temps de réagir.

---

#### `etape_12_security/` — Network Policies + RBAC
**Problème :** Dans un cluster K8s par défaut, tous les pods peuvent communiquer entre eux. Si un pod est compromis, il peut accéder à tous les autres.

**Ce qu'on fait :**
- **Network Policies** (Zero Trust) : chaque pod ne peut communiquer qu'avec ce dont il a besoin
- **RBAC** : ServiceAccounts avec permissions minimales (principe du moindre privilège)
- Audit automatique des permissions

**Concept clé :** *"Never trust, always verify."* — La surface d'attaque est minimisée. Un pod compromis ne peut pas latéralement accéder aux autres.

**Ce qui change :** Le cluster est segmenté. Une compromission d'un composant ne se propage pas aux autres.

---

#### `etape_13_helm/` — Chart Helm : packaging déclaratif
**Problème :** Les manifestes K8s sont dupliqués entre staging, production, CI. Modifier les ressources d'un pod nécessite d'éditer 3 fichiers différents.

**Ce qu'on fait :**
- **Helm Chart** : templatiser tous les manifestes K8s
- `values.yaml` : valeurs par défaut (dev local)
- `values.staging.yaml`, `values.ci.yaml` : surcharges par environnement
- `_helpers.tpl` : fonctions réutilisables (labels, image, etc.)

**Concept clé :** *"Don't repeat yourself — même pour les manifestes K8s."*

```
chart/
├── templates/     # Manifestes templatisés
├── values.yaml    # Valeurs par défaut
├── values.ci.yaml # Surcharges CI (pas d'Ollama, pas de monitoring)
└── Chart.yaml     # Métadonnées du chart
```

**Ce qui change :** Un seul `helm upgrade --set agent.image.tag=v2.1` pour déployer une nouvelle version dans tous les environnements.

---

### Phase 6 — Fiabilité & Observabilité complète

#### `etape_14_slos_alerting/` — SLOs & AlertManager
**Problème :** Les métriques de l'étape 02 montrent des problèmes, mais personne n'est notifié. On découvre les incidents quand les clients appellent.

**Ce qu'on fait :**
- **SLI** (Service Level Indicator) : taux de disponibilité = `success / total`
- **SLO** (Service Level Objective) : disponibilité ≥ 99% sur 30 jours
- **Error Budget** : 432 minutes d'erreurs autorisées par mois
- **Burn Rate** : si les erreurs consomment le budget 14× plus vite → alerte critique
- **AlertManager** : router les alertes vers webhook/Slack, dédupliquer, inhiber

**Concept clé :**
```
Error Budget mensuel = (1 - 0.99) × 30j × 24h × 60min = 432 min
Burn Rate ×14 = budget épuisé en 2h → alerte immédiate
```

**Ce qui change :** On est notifié *avant* que les utilisateurs ne se plaignent, avec suffisamment d'avance pour réagir.

---

#### `etape_15_argo_rollouts/` — Progressive Delivery automatisé
**Problème :** Le canary de l'étape 11 est manuel. Quelqu'un doit surveiller les métriques et décider de promouvoir ou rollback. Ça ne scale pas.

**Ce qu'on fait :**
- **Argo Rollouts** : remplace `kind: Deployment` par `kind: Rollout`
- **AnalysisTemplate** : critères de succès queryés dans Prometheus (disponibilité, taux d'erreur, latence P95)
- **Stratégie canary** : 20% → pause → analyse → 50% → pause → analyse → 80% → 100%
- Rollback automatique si l'analyse échoue

**Concept clé :** *"Automate the boring parts — especially the dangerous ones."*

```yaml
steps:
  - setWeight: 20
  - pause: {duration: 60s}
  - analysis: {templates: [{templateName: traiteur-availability}]}
  - setWeight: 50
  # ... → 100% ou rollback automatique
```

**Ce qui change :** Chaque déploiement est progressif et auto-validé par Prometheus. Si la nouvelle version dégrade les métriques, le rollback est automatique.

---

#### `etape_16_loki/` — Loki : le 3e pilier de l'observabilité
**Problème :** On sait *qu'*il y a un problème (métriques) et *où* il est lent (traces), mais on ne sait pas *pourquoi* exactement. Il manque les logs.

**Ce qu'on fait :**
- **Loki** : stockage de logs indexé par labels (10× plus léger qu'Elasticsearch)
- **Promtail DaemonSet** : collecte automatique des logs de tous les pods K8s
- **LogQL** : langage de requête (comme PromQL mais pour les logs)
- **Derived fields** dans Grafana : `trace_id` dans un log → lien vers Jaeger en 1 clic

**Concept clé :** Les 3 piliers réunis permettent le diagnostic complet en 2 minutes :

```
Incident → Grafana
  1. MÉTRIQUE  : "disponibilité 85% à 14h32"
  2. TRACE     : "span rag.search → trace abc123 → timeout"
  3. LOG       : "ChromaDBError: collection not found after rebuild"
```

**Ce qui change :** L'observabilité est complète. Métriques + Traces + Logs sont corrélés dans Grafana.

---

## L'architecture finale

```
                    ┌────────────────────────────────────────────┐
                    │          Cluster Kubernetes (kind)          │
                    │                                             │
  Utilisateur       │   ┌─────────┐    ┌─────────┐              │
  (voix/web)  ──────┼──▶│  NGINX  │───▶│  Agent  │──▶ Ollama   │
                    │   │ Ingress │    │ (stable)│    (Mistral) │
                    │   │         │10% │         │              │
                    │   │         │───▶│  Agent  │   ChromaDB  │
                    │   └─────────┘    │ (canary)│              │
                    │                  └─────────┘              │
                    │                      │                     │
                    │                 ┌────┴────┐               │
                    │                 │ STT     │ (Blue/Green)   │
                    │                 │ Whisper │               │
                    │                 └────┬────┘               │
                    │                      │                     │
                    │   ┌──────────────────▼──────────────────┐ │
                    │   │         Observabilité                │ │
                    │   │  Prometheus ─── Grafana ─── Loki    │ │
                    │   │  (métriques)   (dashboards) (logs)  │ │
                    │   │                    │                 │ │
                    │   │               Jaeger                 │ │
                    │   │              (traces)                │ │
                    │   └──────────────────────────────────────┘ │
                    │                                             │
                    │   ┌──────────────────────────────────────┐ │
                    │   │         Automatisation               │ │
                    │   │  ArgoCD ── Argo Rollouts ── HPA      │ │
                    │   │  (GitOps)  (prog. delivery) (scale)  │ │
                    │   └──────────────────────────────────────┘ │
                    └────────────────────────────────────────────┘
                              ▲               │
                         Git  │               │ AlertManager
                         (source de vérité)   │ (Slack/webhook)
```

---

## Fil rouge pédagogique

Chaque étape suit la même structure :
1. **Problème** — une vraie limitation de l'étape précédente
2. **Solution** — un outil ou pattern industriel standard
3. **Implémentation** — code fonctionnel, pas théorique
4. **Vérification** — `make demo` ou `make check` pour voir l'effet

Les concepts abordés correspondent à ce que les équipes DevOps/SRE/Platform font réellement en 2024 :
- Kubernetes, Helm, ArgoCD → les standards d'orchestration
- Prometheus, Jaeger, Loki → la stack CNCF d'observabilité
- Argo Rollouts → progressive delivery à la Netflix/Google
- SLOs/Error budgets → la culture SRE de Google

---

## Comment naviguer

```bash
# Chaque étape est autonome et buildable
cd etape_07_kubernetes/
make k8s-up     # démarrer le cluster
make help       # voir toutes les commandes disponibles

# Pour suivre le parcours depuis le début
cd etape_01_simple_vocal_agent/
make dev        # docker compose up

# Pour sauter directement à une étape avancée
cd etape_16_loki/
make helm-install   # déploie tout en une commande
make loki-demo      # démo des 3 piliers
```

**Règle d'or :** chaque dossier `etape_XX/` est un projet complet et indépendant. Il contient son propre `Makefile`, `README.md`, et tout le code nécessaire. On peut commencer à n'importe quelle étape.

---

## Prérequis globaux

| Outil | Version | Étapes concernées |
|-------|---------|-------------------|
| Docker Desktop | ≥ 24 | toutes |
| kind | ≥ 0.23 | 07–16 |
| kubectl | ≥ 1.28 | 07–16 |
| Helm | ≥ 3.14 | 13–16 |
| Python | ≥ 3.11 | toutes |
| GitHub account | — | 08–09 |
| Penpot | web | 00a |

```bash
# Vérifier l'environnement
docker --version
kind version
kubectl version --client
helm version
python3 --version
```
