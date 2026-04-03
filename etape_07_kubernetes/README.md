# Étape 07 — Kubernetes : Replicas, HPA et Rolling Update

> **Prérequis :** avoir complété l'étape 06. Avoir installé `kind` et `kubectl`.
>
> **Concepts clés :**
> - *"Docker Compose orchestre 1 machine. Kubernetes orchestre un cluster."*
> - Pod : l'unité de déploiement K8s (1+ conteneurs qui partagent réseau et volumes)
> - Deployment : déclare l'état désiré (N replicas de tel pod)
> - HPA : autoscale automatiquement selon la charge (CPU, mémoire, métriques custom)
> - Rolling Update : mise à jour sans interruption (pod par pod)

---

## Problème posé

Avec Docker Compose (étapes 01-06), l'agent tourne en **1 seule instance** :

```
Charge normale :  10 requêtes/min  →  1 pod agent = OK
Pic de charge  : 100 requêtes/min  →  1 pod agent = goulot d'étranglement,
                                       latence × 10, timeouts, utilisateurs frustrés
```

Et si le pod crash ? Il n'y a rien pour le remplacer automatiquement.

```bash
# Docker Compose : si le conteneur agent crash...
docker stop traiteur_agent   # → l'agent est mort jusqu'au prochain `make up`
```

**En production, c'est inacceptable** : les utilisateurs ne peuvent pas attendre
qu'un ingénieur relance manuellement le service.

---

## Solution : Kubernetes + HPA

```
Charge normale (CPU < 50%) :  [agent-pod-1] [agent-pod-2]
Pic de charge  (CPU > 50%) :  [agent-pod-1] [agent-pod-2] [agent-pod-3] [agent-pod-4]
                                ↑ HPA détecte et scale out automatiquement

Pod crash :   [agent-pod-1✗] [agent-pod-2]
                ↑ K8s détecte et redémarre immédiatement
              [agent-pod-1-new] [agent-pod-2]   ← rétabli en < 90s
```

---

## Ce qu'on ajoute dans cette étape

| Docker Compose (étape 06) | Kubernetes — étape 07 |
|---|---|
| 1 instance de l'agent | 2 replicas par défaut |
| Scaling manuel (`docker compose scale`) | HPA : scale automatique (2→5 pods) |
| Restart sur crash : `restart: unless-stopped` | Self-healing : K8s redémarre automatiquement |
| Blue/Green STT : nginx reload | Blue/Green STT : `kubectl patch` sur le Service |
| Pas de rolling update natif | Rolling update : `kubectl rollout restart` |
| Pas de resource limits | CPU/memory requests + limits sur chaque pod |

### Nouveaux fichiers

```
etape_07_kubernetes/
├── kind-config.yaml          ← config du cluster kind (port mappings)
└── k8s/
    ├── 00-namespace.yaml     ← namespace "traiteur"
    ├── 01-configmap.yaml     ← variables d'env partagées (équivalent environment:)
    ├── ollama.yaml           ← LLM (PVC + Deployment + Service)
    ├── stt.yaml              ← STT blue + green (Deployments + Service)
    ├── tts.yaml              ← TTS (Deployment + Service)
    ├── agent.yaml            ← Agent (Deployment 2 replicas + Service + HPA)
    ├── ui.yaml               ← UI web (Deployment + Service)
    ├── prometheus.yaml       ← Monitoring (ConfigMap + Deployment + Service)
    └── grafana.yaml          ← Dashboard (ConfigMap + Deployment + Service)
```

---

## Prérequis

```bash
# Installer kind (Kubernetes IN Docker)
# Linux/WSL2 :
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.25.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

# Installer kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/kubectl

# Vérifier
kind version && kubectl version --client
```

---

## Démarrage

```bash
# Déploiement complet (cluster + build + deploy + attente)
make k8s-up

# Télécharger le modèle Mistral (~4 GB)
make k8s-init-ollama

# Vérifier que tout tourne
make k8s-status
```

**Après `make k8s-up` :**
```
  UI         → http://localhost:3000
  Agent      → http://localhost:8000  (load-balancé entre 2 pods)
  Prometheus → http://localhost:9090
  Grafana    → http://localhost:3001
```

---

## Démonstrations

### 1. Observer les replicas

```bash
# Voir les 2 pods agent en cours d'exécution
kubectl get pods -n traiteur -l app=agent

# NAME                     READY   STATUS    RESTARTS   AGE
# agent-7d4b9c8f6-k2p4n   1/1     Running   0          5m
# agent-7d4b9c8f6-x9m3r   1/1     Running   0          5m
```

### 2. Self-healing — K8s redémarre les pods crashés

```bash
# Tuer un pod
kubectl delete pod -n traiteur -l app=agent --field-selector=status.phase=Running --all

# K8s détecte le crash et redémarre automatiquement
kubectl get pods -n traiteur -l app=agent --watch
# agent-xxx   1/1   Running   0   (remplacé automatiquement)
```

### 3. HPA — Autoscaling selon la charge

```bash
# Terminal 1 : surveiller le HPA
make k8s-hpa-watch

# Terminal 2 : générer de la charge
make k8s-stress

# Observer : les pods passent de 2 à 4-5 après ~30s de charge
# Puis redescendent à 2 après ~2min de calme
```

### 4. Rolling Update — zéro downtime

```bash
# Terminal 1 : envoyer des requêtes en continu
while true; do curl -s $(AGENT_URL)/api/text -d '{"text":"test","skip_tts":true}' \
  -H "Content-Type: application/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['response_text'][:50])"; done

# Terminal 2 : déployer la mise à jour
make k8s-rolling-update

# Aucune interruption côté Terminal 1 !
```

### 5. Blue/Green STT — switch via kubectl

```bash
# Voir quel modèle est actif
make k8s-stt-status

# Switch vers green (Whisper small) — plus précis
make k8s-stt-switch-green
# kubectl patch service stt-router -n traiteur -p '{"spec":{"selector":{"color":"green"}}}'

# Rollback vers blue (Whisper base) — plus rapide
make k8s-stt-switch-blue
```

---

## Architecture K8s

```
                    localhost
                       │
         ┌─────────────┼──────────────┐
         │             │              │
      :3000          :8000          :3001
         │             │              │
┌────────────────────────────────────────────┐
│            Cluster kind "traiteur"         │
│  Namespace: traiteur                       │
│                                            │
│  Service:ui:30080  Service:agent:30000     │
│       ↓                  ↓                 │
│  pod:ui          pod:agent-1               │
│                  pod:agent-2    ← HPA      │
│                  pod:agent-3    ← scale    │
│                       ↓                   │
│          Service:ollama  Service:stt-router│
│                ↓              ↓           │
│           pod:ollama    pod:stt-blue  ←─┐ │
│                         pod:stt-green ←─┘ │
│                              ↑            │
│                    B/G via selector patch  │
└────────────────────────────────────────────┘
```

---

## Équivalences Docker Compose ↔ Kubernetes

| Docker Compose | Kubernetes | Description |
|---|---|---|
| `service:` | `Deployment` | Déclare les conteneurs à faire tourner |
| `replicas: 3` | `replicas: 3` | Nombre d'instances |
| `restart: unless-stopped` | `restartPolicy: Always` | Redémarrage automatique |
| `volumes:` | `PVC` / `emptyDir` | Stockage persistant / éphémère |
| `environment:` | `ConfigMap` + `envFrom:` | Variables d'environnement |
| `ports: "8000:8000"` | `NodePort: 30000` | Exposition sur la machine hôte |
| `networks:` (auto) | `Service` (ClusterIP) | Communication entre services |
| `healthcheck:` | `readinessProbe` + `livenessProbe` | Vérification de santé |
| `docker compose scale` | `kubectl scale` / HPA | Scaling manuel / automatique |

---

## Commandes kubectl essentielles

```bash
# Observer
kubectl get pods -n traiteur                     # état des pods
kubectl get pods -n traiteur --watch             # en temps réel
kubectl get hpa -n traiteur                      # état du HPA
kubectl top pods -n traiteur                     # CPU/RAM par pod
kubectl describe pod <nom> -n traiteur           # détail d'un pod

# Logs
kubectl logs -n traiteur -l app=agent --follow   # logs de tous les pods agent
kubectl logs -n traiteur <pod-name>              # logs d'un pod spécifique

# Scaling
kubectl scale deployment/agent -n traiteur --replicas=3  # scale manuel
kubectl rollout restart deployment/agent -n traiteur     # rolling restart

# Debug
kubectl exec -it <pod-name> -n traiteur -- bash  # shell dans un pod
kubectl port-forward svc/agent 9999:8000 -n traiteur  # forward port ad-hoc
```

---

## Commandes utiles

```bash
make k8s-up                # déploiement complet (20-30 min première fois)
make k8s-init-ollama       # télécharge Mistral (~4GB)
make k8s-status            # état de tous les pods/services/HPA

make k8s-hpa-status        # CPU + état HPA
make k8s-hpa-watch         # surveillance temps réel
make k8s-stress            # génère de la charge pour déclencher le HPA
make k8s-scale N=3         # scale manuel à 3 pods

make k8s-rolling-update    # démo rolling update zéro downtime
make k8s-rollout-undo      # rollback du dernier déploiement

make k8s-stt-switch-green  # switch STT → Whisper small
make k8s-stt-switch-blue   # switch STT → Whisper base

make k8s-rag-rebuild       # rebuild RAG (quality gate incluse)
make k8s-rag-status        # état du RAG
make k8s-reload-data       # recharge data/ dans K8s + rebuild RAG

make test-smoke            # tests rapides (< 30s)
make test                  # tous les tests

make k8s-down              # supprime le cluster kind
```

---

## Ce que prépare cette étape

```
Étape 08 → Pipeline CI/CD
  Problème : comment automatiser build → test → déploiement à chaque commit ?
  Solution : pipeline GitHub Actions (ou Gitea local) :
               push → build image → tests → kind cluster éphémère → deploy
  Concepts : CI/CD, artefacts, pipeline as code, GitOps.
```
