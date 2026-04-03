# Étape 15 — Argo Rollouts : Progressive Delivery automatisé

> **Prérequis :** avoir complété l'étape 14 (SLOs & Alerting). Cluster kind actif avec Prometheus.
>
> **Concepts clés :**
> - *"Automate the boring parts — especially the dangerous ones."*
> - Rollout : ressource Argo qui remplace le Deployment K8s
> - AnalysisTemplate : critères de succès d'un déploiement (requêtes Prometheus)
> - AnalysisRun : exécution d'une analyse à chaque étape du rollout
> - Promotion automatique / Rollback automatique selon les métriques
> - Connexion directe avec les SLOs définis à l'étape 14

---

## Problème posé

À l'étape 11, on a fait du canary **manuel** avec NGINX :

```bash
# scripts/canary-promote.sh (étape 11) :
for WEIGHT in 10 20 40 80 100; do
    kubectl patch ingress agent-canary-ingress \
        -p '{"metadata":{"annotations":{"nginx.ingress.kubernetes.io/canary-weight":"'$WEIGHT'"}}}'
    sleep 30
    # vérification manuelle des métriques...
    if error_rate > 5%; then rollback; fi
done
```

À l'étape 14, on a défini des SLOs avec Prometheus. Mais personne n'a encore **branché les deux** ensemble.

**Résultat** : un humain doit surveiller les métriques ET décider de promouvoir ou rollbacker.

---

## Solution : Argo Rollouts

```yaml
# Un seul fichier YAML remplace tout le script canary-promote.sh :
strategy:
  canary:
    steps:
      - setWeight: 20
      - pause: {duration: 60s}
      - analysis:                        # ← interroge Prometheus
          templates:
            - templateName: traiteur-availability
      - setWeight: 50
      - pause: {duration: 60s}
      - analysis:
          templates:
            - templateName: traiteur-availability
      # → promotion automatique à 100% si tout va bien
      # → rollback automatique si availability < 0.99 ou error-rate > 5%
```

```
Avant (étape 11) :                      Après (étape 15) :
  humain → surveille Grafana              Argo Rollouts → interroge Prometheus
         → décide de promouvoir                         → décide automatiquement
         → exécute le script                            → 0 intervention humaine
         → rollback si ça casse                         → rollback si SLO violé
```

---

## Les 3 nouvelles ressources K8s

### 1. `Rollout` — remplace le `Deployment`

```yaml
apiVersion: argoproj.io/v1alpha1   # ← CRD Argo (pas K8s natif)
kind: Rollout                       # ← remplace kind: Deployment
metadata:
  name: agent
spec:
  replicas: 2
  strategy:
    canary:               # ← au lieu de rollingUpdate
      steps: [...]
  template:
    # ← identique à un Deployment (même pod spec)
```

```
Deployment standard :                  Rollout Argo :
  v1 → v2                               v1 → 20% v2 → analyse → 50% → analyse → 100%
  Rolling update (tous en même temps)   Progression contrôlée par les métriques
  Pas d'analyse                         Rollback auto si SLO violé
```

### 2. `AnalysisTemplate` — les critères de succès

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: traiteur-availability
spec:
  metrics:
    - name: availability
      interval: 30s
      count: 4                    # 4 mesures × 30s = 2 min d'analyse
      successCondition: result[0] >= 0.99   # ← notre SLO étape 14
      failureLimit: 1             # 1 seule mesure sous le seuil → échec
      provider:
        prometheus:
          address: http://prometheus:9090
          query: |
            sum(rate(conversations_total{status="success"}[2m]))
            /
            sum(rate(conversations_total[2m]))
```

### 3. `AnalysisRun` — créé automatiquement

```
À chaque étape "analysis:" du Rollout, Argo Rollouts crée automatiquement
un AnalysisRun qui exécute les requêtes Prometheus et détermine le résultat.

kubectl get analysisrun -n traiteur
  NAME                              PHASE        AGE
  agent-abc123-2-traiteur-avail     Successful   5m
  agent-def456-4-traiteur-avail     Running      30s
```

---

## Démarrage rapide

```bash
# Installer Argo Rollouts + AnalysisTemplate + activer le mode Rollout :
make rollout-install

# Vérifier l'état :
make rollout-status

# Démo d'un déploiement progressif réussi (durée ~6-8 min) :
make rollout-demo

# Démo de rollback automatique (version cassée) :
make rollout-break
```

---

## Déclencher un déploiement progressif

```bash
# Méthode 1 : changer l'image (le cas normal en production)
kubectl argo rollouts set image rollout/agent \
    agent=traiteur-agent:v2 -n traiteur

# Méthode 2 : helm upgrade (recommandé avec Helm)
helm upgrade traiteur ./chart --set agent.image.tag=v2

# Observer la progression en temps réel :
kubectl argo rollouts get rollout agent -n traiteur --watch

# Sortie :
# Name:            agent
# Namespace:       traiteur
# Status:          ॥ Paused
# Strategy:        Canary
#   Step:          3/9
#   SetWeight:     20
#   ActualWeight:  20
# Images:          traiteur-agent:latest (stable)
#                  traiteur-agent:v2 (canary, weight: 20)
# Replicas:
#   Desired:       2
#   Current:       2
#   Updated:       1
#   Ready:         2
```

---

## Scénarios de la démo

### Scénario A : Déploiement réussi

```
20% canary → pause 60s → AnalysisRun (availability ✓, error-rate ✓)
→ 50% canary → pause 60s → AnalysisRun (✓)
→ 80% canary → pause 30s → AnalysisRun (✓)
→ 100% → Rollout Healthy ✓
```

### Scénario B : Rollback automatique

```
20% canary (version cassée)
→ pause 60s
→ AnalysisRun : availability = 0.60 < 0.99 → FAILED
→ Rollout passe en Degraded
→ Rollback automatique : 100% stable
→ Alerte AlertManager → Slack/webhook
```

### Commandes de contrôle manuel

```bash
# Forcer la promotion à l'étape suivante (bypass la pause) :
kubectl argo rollouts promote agent -n traiteur
make rollout-promote

# Rollback manuel immédiat :
kubectl argo rollouts abort agent -n traiteur
make rollout-abort

# Inspecter un AnalysisRun :
kubectl describe analysisrun <nom> -n traiteur
```

---

## Intégration Helm

```
# values.yaml
rollout:
  enabled: false          # false = Deployment standard
  pauseDuration: "60s"
  analysis:
    availabilityThreshold: "0.99"   # reprend les SLOs de l'étape 14
    errorRateThreshold: "0.05"
```

```bash
# Activer :
make rollout-on
# ↓ helm upgrade --set rollout.enabled=true
# → Helm supprime le Deployment, crée le Rollout

# Désactiver :
make rollout-off
# → Retour au Deployment standard
```

---

## Comparaison : Canary manuel vs Argo Rollouts

| | Étape 11 (canary NGINX) | Étape 15 (Argo Rollouts) |
|--|---|---|
| Déclenchement | Manuel (`bash canary-setup.sh`) | Automatique (changement d'image) |
| Progression | Script bash + cron | Argo Rollouts controller |
| Décision promoton | Humain vérifie Grafana | PromQL automatique |
| Rollback | Manuel (`bash canary-step.sh 0`) | Automatique si SLO violé |
| Visibilité | `kubectl get ingress` | `kubectl argo rollouts get rollout` |
| GitOps compatible | Partiellement | Nativement (ArgoCD + Argo Rollouts) |

---

## Nouveaux fichiers

```
argo-rollouts/
  rollout-agent.yaml          → Rollout K8s standalone (référence)
  analysis-template.yaml      → AnalysisTemplate standalone

chart/templates/
  rollout.yaml                → Helm : Rollout + AnalysisTemplate (si rollout.enabled)
  agent.yaml                  → MODIFIÉ : Deployment conditionnel (si NOT rollout.enabled)

scripts/
  rollout-install.sh          → installe Argo Rollouts + configure Helm
  rollout-demo.sh             → démo : succès / rollback / manuel

chart/values.yaml             → +rollout.*
Makefile                      → rollout-install/status/demo/break/promote/abort/on/off
README.md                     → doc complète
```

---

## Pour aller plus loin

- **NGINX traffic routing** — routing précis basé sur les poids (vs replica-based)
- **Blue/Green avec Argo Rollouts** — `strategy: blueGreen` au lieu de `canary`
- **ArgoCD + Argo Rollouts** — ArgoCD déploie le Rollout, Argo Rollouts gère la progression
- **Experiment** — tester plusieurs versions en parallèle (A/B testing)
- **Argo Events** — déclencher un Rollout depuis un webhook GitHub
