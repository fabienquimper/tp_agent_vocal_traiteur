# Étape 13 — Helm : Packaging et déploiement déclaratif

> **Prérequis :** avoir complété l'étape 12 (Sécurité). Cluster kind actif.
>
> **Concepts clés :**
> - *"Don't repeat yourself — même pour les manifestes K8s."*
> - Helm : gestionnaire de paquets pour Kubernetes
> - Chart : archive d'un ensemble de ressources K8s templatisées
> - Values : configuration externalisée (dev / staging / prod / ci)
> - Release : une instance déployée d'un chart (versionnée, rollback possible)
> - Named templates (`_helpers.tpl`) : éviter la répétition

---

## Problème posé

Depuis l'étape 07, nous avons accumulé **15+ fichiers YAML** :

```
k8s/
├── 00-namespace.yaml
├── 01-configmap.yaml
├── agent.yaml            # namespace "traiteur" hardcodé
├── ollama.yaml           # replicas: 2 hardcodé
├── stt.yaml              # model: "base" hardcodé
├── tts.yaml
├── ui.yaml
├── prometheus.yaml       # retention: 7d hardcodé
├── grafana.yaml          # adminPassword: "admin" hardcodé
├── jaeger.yaml
├── agent-canary.yaml
├── ingress.yaml
├── rbac/rbac.yaml
└── security/network-policies.yaml
```

**Problèmes** :
1. `namespace: traiteur` copié/collé dans 50+ endroits
2. Pour déployer en staging, il faut modifier des fichiers → erreurs, divergences
3. Impossible de savoir quelle version est déployée en production
4. Rollback = `git revert` + `kubectl apply` manuel
5. Activer/désactiver le canary = éditer manuellement 3 fichiers

---

## Solution : Helm

```
Avant (kubectl apply) :
  kubectl apply -f k8s/00-namespace.yaml
  kubectl apply -f k8s/01-configmap.yaml
  kubectl apply -f k8s/agent.yaml
  ... (15 commandes)

Après (helm install) :
  helm install traiteur ./chart
  # Une commande, tout est déployé, versionné, rollbackable
```

### La magie des values

```yaml
# values.yaml (production — défauts)    vs    values.staging.yaml (surcharges)
agent:                                        agent:
  replicaCount: 2                               replicaCount: 1
  env:                                          env:
    ragQualityThreshold: "0.8"                    ragQualityThreshold: "0.7"
  hpa:                                          hpa:
    enabled: true                                 enabled: false
monitoring:
  grafana:
    enabled: true                               grafana:
                                                  enabled: false
```

```bash
# Déployer en staging :
helm upgrade traiteur ./chart -f values.staging.yaml
# AUCUN fichier modifié, changements déclaratifs

# Rollback en 1 commande :
helm rollback traiteur
```

---

## Structure du chart

```
chart/
├── Chart.yaml                    # métadonnées (nom, version, appVersion)
├── values.yaml                   # valeurs par défaut (production)
├── values.staging.yaml           # surcharges staging
├── values.ci.yaml                # surcharges CI (sans Ollama, sans monitoring)
└── templates/
    ├── _helpers.tpl              # fonctions réutilisables (labels, image, url)
    ├── configmap.yaml            # ConfigMap traiteur-config
    ├── agent.yaml                # Deployment + Service + HPA + Canary (conditionnels)
    ├── ollama.yaml               # PVC + Deployment + Service  (si ollama.enabled)
    ├── stt.yaml                  # Blue + Green + Router (selector dynamique)
    ├── tts.yaml                  # Deployment + Service
    ├── monitoring.yaml           # Prometheus + Grafana    (si *.enabled)
    ├── tracing.yaml              # Jaeger                  (si jaeger.enabled)
    ├── rbac.yaml                 # ServiceAccounts + Roles (si rbac.create)
    ├── network-policies.yaml     # Zero Trust NetworkPolicies (si *.enabled)
    └── NOTES.txt                 # instructions post-install (helm affiche ça)
```

---

## Concepts Helm illustrés dans ce chart

### 1. Templatisation simple

```yaml
# Avant (k8s/agent.yaml étape 07) :
replicas: 2

# Après (chart/templates/agent.yaml étape 13) :
replicas: {{ .Values.agent.replicaCount }}
```

### 2. Fonctions utilitaires (`_helpers.tpl`)

```yaml
# Plutôt que répéter ces 4 labels dans CHAQUE ressource :
helm.sh/chart: traiteur-1.0.0
app.kubernetes.io/managed-by: Helm
app.kubernetes.io/instance: traiteur
app.kubernetes.io/version: "2.0.0"

# On écrit une seule fois :
{{- include "traiteur.labels" . | nindent 4 }}
```

### 3. Blocs conditionnels

```yaml
# Le HPA n'existe en staging que si hpa.enabled=true dans values.staging.yaml
{{- if .Values.agent.hpa.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
...
{{- end }}
```

### 4. Blue/Green STT — selector dynamique

```yaml
# stt-router pointe vers la couleur active
spec:
  selector:
    app: stt
    color: {{ .Values.stt.activeColor }}   # "blue" ou "green"
```

```bash
# Basculer sans redéployer les pods STT :
helm upgrade traiteur ./chart --set stt.activeColor=green
# → Seul le Service stt-router est mis à jour (1 seconde)
# → Équivalent à kubectl patch, mais versionné dans Helm
```

### 5. toYaml — injecter des objets YAML complexes

```yaml
# Les ressources CPU/RAM restent lisibles dans values.yaml :
resources:
  {{- toYaml .Values.agent.resources | nindent 12 }}
# Au lieu de : cpu: {{ .Values.agent.resources.requests.cpu }} ...
```

---

## Démarrage rapide

```bash
# Déploiement production (1 commande) :
make helm-install

# Déploiement staging :
make helm-install ENV=staging

# Déploiement CI (sans Ollama) :
make helm-install ENV=ci
```

---

## Workflow de mise à jour

```bash
# 1. Voir ce qui va changer (avant l'upgrade) :
make helm-diff

# 2. Mettre à jour :
make helm-upgrade

# 3. Si problème → rollback immédiat :
make helm-rollback

# 4. Historique des versions :
make helm-history
```

---

## Opérations sans redéploiement complet

```bash
# Basculer STT vers Whisper small (green) :
make helm-stt-green
# Revenir à Whisper base (blue) :
make helm-stt-blue

# Activer le canary (10% trafic) :
make helm-canary-on
# Désactiver le canary :
make helm-canary-off

# Inspecter les valeurs actives :
make helm-values
```

---

## Comparaison finale : avant/après Helm

| Opération | Étape 07 (kubectl) | Étape 13 (Helm) |
|-----------|-------------------|-----------------|
| 1er déploiement | `kubectl apply -f k8s/` | `helm install traiteur ./chart` |
| Déployer en staging | Modifier les fichiers | `helm upgrade -f values.staging.yaml` |
| Rollback | `git revert` + `kubectl apply` | `helm rollback traiteur` |
| Activer canary | Éditer 3 fichiers + apply | `helm upgrade --set canary.enabled=true` |
| Changer modèle STT | `kubectl patch service stt-router` | `helm upgrade --set stt.activeColor=green` |
| Version déployée | `git log` (approximatif) | `helm history traiteur` |
| Supprimer tout | `kubectl delete -f k8s/` (ordre important) | `helm uninstall traiteur` |

---

## Pour aller plus loin

- **Helm Hub** : charts publics (Prometheus Operator, cert-manager, ArgoCD...)
- **Helmfile** : déclarer plusieurs charts dans un fichier (orchestration)
- **helm-secrets** : chiffrer les valeurs sensibles dans values.yaml
- **chart testing** (`ct lint-and-install`) : CI pour les charts Helm
