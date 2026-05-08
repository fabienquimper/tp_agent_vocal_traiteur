# Étape 09 — GitOps avec ArgoCD

> **Prérequis :** avoir complété l'étape 08. Un dépôt GitHub public (gratuit).
>
> **Concepts clés :**
> - *"Git est la seule source de vérité. Toute modification hors de Git est une dérive."*
> - GitOps : l'état désiré du cluster est décrit dans Git, pas dans des scripts
> - Push model (CI/CD) vs Pull model (GitOps)
> - Reconciliation loop : ArgoCD surveille en permanence et corrige les dérives
> - selfHeal : restauration automatique des modifications manuelles

---

## Problème posé

Avec le pipeline CD de l'étape 08, le déploiement fonctionne ainsi :

```
git push
   │
   ▼
GitHub Actions (CI)
   │
   ▼  kubectl apply (PUSH depuis le CI vers le cluster)
Cluster Kubernetes
```

Ce modèle **push** a des limitations :

| Problème | Conséquence |
|---|---|
| Un opérateur fait `kubectl scale` en urgence | L'état du cluster diverge de Git (dérive invisible) |
| GitHub Actions tombe en panne | Plus aucun déploiement possible |
| La CI a accès au cluster (kubeconfig) | Surface d'attaque élargie |
| Aucun historique de "qui a déployé quoi" | Audit impossible |
| `kubectl apply` n'est pas idempotent | Ressources orphelines possibles |

---

## Solution : le modèle GitOps (Pull)

```
git push
   │
   ▼
Dépôt Git (GitHub)
   │
   │  ArgoCD surveille (toutes les 3 min)
   ▼
ArgoCD (dans le cluster)
   │
   │  ArgoCD PULL les manifestes et les applique
   ▼
Cluster Kubernetes

                    ← selfHeal ←
Cluster ──── ArgoCD détecte dérive ──── kubectl edit (modification manuelle)
```

**Le cluster vient CHERCHER son état dans Git**, au lieu que le CI le pousse.

---

## Ce qu'on ajoute dans cette étape

| Étape 08 (CI/CD push) | Étape 09 (GitOps pull) |
|---|---|
| GitHub Actions `kubectl apply` | ArgoCD reconciliation loop |
| Pas de détection de dérive | selfHeal : restaure les modifications manuelles |
| Historique dans GitHub Actions | Historique dans ArgoCD (syncs, rollbacks) |
| CI a accès au cluster (kubeconfig secret) | ArgoCD est dans le cluster, pas besoin d'exposer kube API |
| Rollback = re-run le CI | Rollback = `argocd app rollback <revision>` |

### Nouveaux fichiers

```
etape_09_gitops/
├── argocd/
│   ├── application.yaml     ← Application CR (source=k8s/, destination=cluster)
│   └── project.yaml         ← AppProject (scoping des permissions ArgoCD)
├── scripts/
│   ├── argocd-setup.sh      ← Installation ArgoCD + création Application
│   └── argocd-demo-drift.sh ← Démonstration selfHeal en direct
└── kind-config.yaml         ← Ajout port 30081 → 8080 (ArgoCD UI)
```

---

## Démarrage rapide

```bash
# Prérequis : cluster kind actif (étape 07/08)
make k8s-up

# 1. Installer ArgoCD et créer l'Application
#    (pointer sur votre fork du dépôt)
make argocd-setup REPO_URL=https://github.com/VOTRE_USER/tp_agent_vocal_traiteur.git

# 2. Ouvrir l'UI ArgoCD
make argocd-ui
# → https://localhost:8080  (admin / voir mot de passe affiché)

# 3. Démonstration de selfHeal
make argocd-demo-drift
```

---

## Architecture ArgoCD

```
┌─────────────────────────── Cluster kind "traiteur" ─────────────────────────┐
│                                                                               │
│  namespace: argocd                    namespace: traiteur                     │
│  ┌─────────────────────────┐          ┌────────────────────────────────────┐  │
│  │  argocd-server          │          │  agent (2 replicas)                │  │
│  │  argocd-repo-server     │─────────▶│  stt-blue / stt-green              │  │
│  │  argocd-application-    │  apply   │  tts                               │  │
│  │    controller           │          │  ollama                            │  │
│  │  argocd-dex-server      │          │  prometheus / grafana              │  │
│  └─────────────────────────┘          └────────────────────────────────────┘  │
│           │                                                                   │
│           │  git pull (toutes les 3 min)                                      │
│           │                                                                   │
└───────────┼───────────────────────────────────────────────────────────────────┘
            │
            ▼
    GitHub (k8s/ directory)
    application.yaml → source.path = "k8s"
```

---

## Les deux ressources ArgoCD clés

### AppProject (`argocd/project.yaml`)

Définit **les permissions** d'un groupe d'Applications :
- Quels dépôts Git sont autorisés comme source
- Quels namespaces/clusters sont autorisés comme destination
- Quelles ressources K8s peuvent être créées

```yaml
# En production, on limiterait :
sourceRepos:
  - 'https://github.com/mon-org/tp_agent_vocal_traiteur.git'  # URL exacte
destinations:
  - namespace: traiteur
    server: https://kubernetes.default.svc
```

### Application (`argocd/application.yaml`)

Déclare **le lien** entre source Git et destination K8s :

```yaml
spec:
  source:
    repoURL: https://github.com/VOTRE_USER/tp_agent_vocal_traiteur.git
    targetRevision: main    # branche suivie
    path: k8s               # dossier des manifestes

  destination:
    namespace: traiteur     # où déployer

  syncPolicy:
    automated:
      prune: true           # supprime ce qui n'est plus dans Git
      selfHeal: true        # ← RESTAURE toute modification manuelle
```

---

## Démonstrations

### 1. Le workflow GitOps normal

```bash
# Modifier un manifeste K8s
vim k8s/agent.yaml
# → changer replicas: 2 → replicas: 3

# Pousser sur GitHub
git add k8s/agent.yaml
git commit -m "scale agent to 3 replicas"
git push

# ArgoCD détecte dans les 3 minutes (ou forcer)
make argocd-sync

# Vérifier
make argocd-status
kubectl get pods -n traiteur -l app=agent
# → 3 pods agent running
```

### 2. Démonstration de selfHeal (dérive)

```bash
make argocd-demo-drift
# → Le script fait kubectl scale manuellement
# → ArgoCD détecte la dérive
# → ArgoCD restaure automatiquement
# → Preuve que Git = seule source de vérité
```

Manuellement :

```bash
# Créer une dérive : modifier le cluster directement
kubectl scale deployment agent -n traiteur --replicas=5

# Observer dans l'UI : Application passe en "OutOfSync"
make argocd-ui

# Attendre 3 min OU forcer la réconciliation
make argocd-sync

# Vérifier : replicas est revenu à la valeur Git (2)
kubectl get deployment agent -n traiteur
```

### 3. Rollback via ArgoCD

```bash
# Voir l'historique des syncs
argocd app history traiteur

# OUTPUT :
# ID  DATE                  REVISION
# 0   2025-01-15 10:23:45   abc1234 (main)
# 1   2025-01-15 11:02:11   def5678 (main)
# 2   2025-01-15 14:30:00   ghi9012 (main)  ← actuel

# Revenir à la révision 1
argocd app rollback traiteur 1
# → ArgoCD redéploie les manifestes du commit def5678
```

### 4. Diff avant de pousser

```bash
# Modifier un manifeste localement
vim k8s/agent.yaml

# Voir ce qui changerait AVANT de pousser
make argocd-diff
# → Affiche le diff entre l'état Git actuel et l'état cluster
# → Utile pour valider une modification complexe
```

### 5. Désactiver temporairement l'auto-sync

```bash
# Désactiver l'auto-sync (pour une maintenance)
argocd app set traiteur --sync-policy none

# Faire des modifications manuelles sans qu'ArgoCD les écrase...

# Réactiver l'auto-sync
argocd app set traiteur --sync-policy automated \
    --auto-prune --self-heal
```

---

## Push model vs Pull model — résumé

```
Push model (étape 08 — CI/CD) :
  ┌──────────┐    push    ┌───────────────┐    kubectl apply    ┌─────────┐
  │ dev push │──────────▶│ GitHub Actions │───────────────────▶│ Cluster │
  └──────────┘            └───────────────┘                     └─────────┘
  + simple à comprendre
  + feedback immédiat dans le CI
  - CI doit avoir accès au cluster (kubeconfig = secret)
  - dérives non détectées
  - rollback = re-run le CI

Pull model (étape 09 — GitOps) :
  ┌──────────┐    push    ┌────────┐
  │ dev push │──────────▶│  Git   │
  └──────────┘            └────────┘
                              │
                              │  pull (toutes les 3 min)
                              ▼
                   ┌────────────────────┐    apply    ┌─────────┐
                   │ ArgoCD (in-cluster)│────────────▶│ Cluster │
                   └────────────────────┘             └─────────┘
  + pas de kubeconfig exposé en CI
  + dérives détectées et corrigées automatiquement
  + rollback simple (argocd app rollback)
  + audit trail complet dans ArgoCD
  - latence de 3 min (configurable)
  - plus complexe à installer
```

---

## Commandes utiles

```bash
# ── ArgoCD ────────────────────────────────────────────────────────────────────
make argocd-setup REPO_URL=<url>  # installation initiale
make argocd-status                # sync + health status
make argocd-diff                  # Git ↔ cluster diff
make argocd-sync                  # sync manuel
make argocd-rollback              # rollback interactif
make argocd-password              # mot de passe admin
make argocd-ui                    # ouvrir l'UI
make argocd-demo-drift            # démonstration selfHeal

# ── argocd CLI (si installé) ──────────────────────────────────────────────────
argocd app list                   # toutes les applications
argocd app get traiteur           # détails de l'application
argocd app history traiteur       # historique des syncs
argocd app logs traiteur          # logs des ressources
argocd app set traiteur --sync-policy none  # désactiver auto-sync

# ── K8s (hérité) ──────────────────────────────────────────────────────────────
make k8s-up                       # créer le cluster + déployer
make k8s-status                   # état des pods/services
make test-smoke                   # tests rapides
```

---

## Ce que prépare cette étape

```
Étape 10 → Observabilité avancée : traces distribuées avec OpenTelemetry
  Problème : logs + métriques (étape 02) ne suffisent pas pour debugger
             des problèmes qui traversent plusieurs services.
  Solution : traces end-to-end (voice → agent → ollama → réponse)
  Concepts : OpenTelemetry, Jaeger, trace ID, span, propagation de contexte.
```
